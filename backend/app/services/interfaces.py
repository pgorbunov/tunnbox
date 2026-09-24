"""Interface lifecycle: CRUD, up/down, config rendering, reconcile.

Every mutation commits the database change first and only then renders the
`.conf` and talks to the WireGuard backend (`apply`). If the backend step
fails the request returns 502, but the file on disk has already been
re-rendered from the committed database state, so the two never diverge.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from app.context import AppContext
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.security import iso, now_iso, utcnow
from app.db.connection import connect
from app.db.repos import interfaces as repo
from app.db.repos import peers as peers_repo
from app.schemas.interfaces import InterfaceCreate, InterfaceUpdate
from app.services import audit
from app.services.wireguard import keys
from app.services.wireguard.renderer import render_server_config, write_config_atomic

logger = logging.getLogger(__name__)

ONLINE_WINDOW = timedelta(seconds=180)
RESTART_FIELDS = {"address", "listen_port", "mtu", "post_up", "post_down"}


def conf_path(ctx: AppContext, name: str) -> Path:
    return ctx.settings.config_dir / f"{name}.conf"


async def _require(db: aiosqlite.Connection, name: str) -> dict[str, Any]:
    row = await repo.get_by_name(db, name)
    if row is None:
        raise NotFound("Interface not found")
    return row


async def to_response(ctx: AppContext, db: aiosqlite.Connection, row: dict[str, Any]) -> dict[str, Any]:
    summary = await repo.peer_summary(db, row["id"], iso(utcnow() - ONLINE_WINDOW))
    return {
        "id": row["id"],
        "name": row["name"],
        "public_key": row["public_key"],
        "address": row["address"],
        "listen_port": row["listen_port"],
        "dns": row["dns"],
        "mtu": row["mtu"],
        "post_up": row["post_up"],
        "post_down": row["post_down"],
        "public_endpoint": row["public_endpoint"],
        "enabled": bool(row["enabled"]),
        "is_active": await ctx.backend.is_active(row["name"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        **summary,
    }


async def _response_by_name(ctx: AppContext, name: str) -> dict[str, Any]:
    async with connect(ctx.db_path) as db:
        return await to_response(ctx, db, await _require(db, name))


async def _audit(ctx: AppContext, actor: audit.Actor, action: str, target: str, details: dict[str, Any] | None = None) -> None:
    async with connect(ctx.db_path) as db:
        await audit.add(db, actor, action, target=target, details=details)


# --- rendering / applying -----------------------------------------------------------


def _scripts_for_render(ctx: AppContext, row: dict[str, Any]) -> tuple[str | None, str | None]:
    """PostUp/PostDown are rendered only when WG_ALLOW_CUSTOM_SCRIPTS is on."""
    if ctx.settings.wg_allow_custom_scripts:
        return row["post_up"], row["post_down"]
    if (row["post_up"] or row["post_down"]) and row["name"] not in ctx.scripts_warned:
        ctx.scripts_warned.add(row["name"])
        logger.warning("Interface %s has PostUp/PostDown but WG_ALLOW_CUSTOM_SCRIPTS is false; scripts omitted", row["name"])
    return None, None


async def render(ctx: AppContext, db: aiosqlite.Connection, row: dict[str, Any]) -> str:
    """Render the server config from the DB and write it atomically (0600)."""
    peers = await peers_repo.list_for_interface(db, row["id"])
    rendered_peers = [
        {
            "name": p["name"],
            "public_key": p["public_key"],
            "preshared_key": ctx.secrets.decrypt(p["preshared_key_enc"]) if p["preshared_key_enc"] else None,
            "allowed_ips": p["allowed_ips"],
            "persistent_keepalive": p["persistent_keepalive"],
        }
        for p in peers
        if p["enabled"]
    ]
    post_up, post_down = _scripts_for_render(ctx, row)
    text = render_server_config(
        {
            "private_key": ctx.secrets.decrypt(row["private_key_enc"]),
            "address": row["address"],
            "listen_port": row["listen_port"],
            "dns": row["dns"],
            "mtu": row["mtu"],
            "post_up": post_up,
            "post_down": post_down,
            "public_endpoint": row["public_endpoint"],
        },
        rendered_peers,
    )
    write_config_atomic(conf_path(ctx, row["name"]), text)
    return text


async def apply(ctx: AppContext, name: str, *, restart: bool = False) -> None:
    """Re-render from committed state and push it to the running interface.

    Raises `BackendError` (502) if the backend refuses; the file is already
    consistent with the database at that point.
    """
    async with connect(ctx.db_path) as db:
        row = await repo.get_by_name(db, name)
        if row is None:
            return
        await render(ctx, db, row)
    active = await ctx.backend.is_active(name)
    if restart and active:
        await ctx.backend.down(name)
        if row["enabled"]:
            await ctx.backend.up(name)
    elif active:
        await ctx.backend.sync(name)


# --- queries --------------------------------------------------------------------------


async def list_interfaces(ctx: AppContext) -> list[dict[str, Any]]:
    async with connect(ctx.db_path) as db:
        rows = await repo.list_all(db)
        return [await to_response(ctx, db, r) for r in rows]


async def get_interface(ctx: AppContext, name: str) -> dict[str, Any]:
    return await _response_by_name(ctx, name)


async def server_config_text(ctx: AppContext, name: str) -> str:
    async with connect(ctx.db_path) as db:
        row = await _require(db, name)
        return await render(ctx, db, row)


# --- mutations ------------------------------------------------------------------------


def _check_scripts(ctx: AppContext, is_admin: bool, post_up: str | None, post_down: str | None) -> None:
    if not (post_up or post_down):
        return
    if not ctx.settings.wg_allow_custom_scripts:
        raise BadRequest("Custom PostUp/PostDown scripts are disabled (WG_ALLOW_CUSTOM_SCRIPTS)", code="scripts_disabled")
    if not is_admin:
        raise Forbidden("Only admins may set PostUp/PostDown scripts")


async def create_interface(ctx: AppContext, actor: audit.Actor, data: InterfaceCreate, *, is_admin: bool) -> dict[str, Any]:
    _check_scripts(ctx, is_admin, data.post_up, data.post_down)
    private_key, public_key = keys.generate_keypair()
    async with connect(ctx.db_path, immediate=True) as db:
        if await repo.get_by_name(db, data.name):
            raise Conflict("Interface name already exists")
        if await repo.port_in_use(db, data.listen_port):
            raise Conflict("Listen port already in use")
        row = await repo.create(
            db,
            now_iso(),
            name=data.name,
            private_key_enc=ctx.secrets.encrypt(private_key),
            public_key=public_key,
            address=data.address,
            listen_port=data.listen_port,
            dns=data.dns,
            mtu=data.mtu,
            post_up=data.post_up,
            post_down=data.post_down,
            public_endpoint=data.public_endpoint,
            enabled=data.enabled,
        )
        await audit.add(db, actor, "interface.created", target=row["name"], details={"address": data.address, "listen_port": data.listen_port})
    await apply(ctx, row["name"])
    if data.enabled:
        await ctx.backend.up(row["name"])
    return await _response_by_name(ctx, row["name"])


async def update_interface(ctx: AppContext, actor: audit.Actor, name: str, data: InterfaceUpdate, *, is_admin: bool) -> dict[str, Any]:
    changes = data.model_dump(exclude_unset=True)
    if "post_up" in changes or "post_down" in changes:
        if not is_admin:
            raise Forbidden("Only admins may change PostUp/PostDown scripts")
        _check_scripts(ctx, is_admin, changes.get("post_up"), changes.get("post_down"))
    async with connect(ctx.db_path, immediate=True) as db:
        row = await _require(db, name)
        if "listen_port" in changes and changes["listen_port"] != row["listen_port"]:
            if await repo.port_in_use(db, changes["listen_port"], exclude_id=row["id"]):
                raise Conflict("Listen port already in use")
        enabled_change = changes.pop("enabled", None)
        effective = {k: v for k, v in changes.items() if row.get(k) != v}
        if enabled_change is not None and bool(row["enabled"]) == enabled_change:
            enabled_change = None
        now = now_iso()
        if effective:
            await repo.update(db, row["id"], now, **effective)
            await audit.add(db, actor, "interface.updated", target=name, details={"fields": sorted(effective)})
        if enabled_change is not None:
            await repo.update(db, row["id"], now, enabled=enabled_change)
    await apply(ctx, name, restart=bool(RESTART_FIELDS & effective.keys()))
    if enabled_change is not None:
        await _set_live_state(ctx, actor, name, enabled_change)
    return await _response_by_name(ctx, name)


async def _set_live_state(ctx: AppContext, actor: audit.Actor, name: str, up: bool) -> None:
    active = await ctx.backend.is_active(name)
    if up and not active:
        await ctx.backend.up(name)
        await _audit(ctx, actor, "interface.up", name)
    elif not up and active:
        await ctx.backend.down(name)
        await _audit(ctx, actor, "interface.down", name)


async def set_interface_state(ctx: AppContext, actor: audit.Actor, name: str, up: bool) -> dict[str, Any]:
    async with connect(ctx.db_path, immediate=True) as db:
        row = await _require(db, name)
        if bool(row["enabled"]) != up:
            await repo.update(db, row["id"], now_iso(), enabled=up)
    await apply(ctx, name)
    await _set_live_state(ctx, actor, name, up)
    return await _response_by_name(ctx, name)


async def delete_interface(ctx: AppContext, actor: audit.Actor, name: str) -> None:
    async with connect(ctx.db_path) as db:
        await _require(db, name)
    if await ctx.backend.is_active(name):
        await ctx.backend.down(name)
    async with connect(ctx.db_path, immediate=True) as db:
        row = await _require(db, name)
        peer_count = await peers_repo.count_for_interface(db, row["id"])
        await repo.delete(db, row["id"])
        await audit.add(db, actor, "interface.deleted", target=name, details={"peers": peer_count})
    path = conf_path(ctx, name)
    if path.exists():
        path.unlink()


# --- startup ----------------------------------------------------------------------------


async def reconcile(ctx: AppContext) -> None:
    """Startup job: import legacy configs, render everything, bring enabled interfaces up."""
    from app.services import importer

    await importer.import_legacy_configs(ctx)
    async with connect(ctx.db_path) as db:
        rows = await repo.list_all(db)
    for row in rows:
        name = row["name"]
        try:
            await apply(ctx, name)
            if row["enabled"] and not await ctx.backend.is_active(name):
                await ctx.backend.up(name)
        except Exception:  # noqa: BLE001 - keep reconciling the others
            logger.exception("Reconcile failed for interface %s", name)
