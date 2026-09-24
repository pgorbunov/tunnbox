"""Interface lifecycle: CRUD, up/down, config rendering, reconcile."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from app.context import AppContext
from app.core.errors import BadRequest, Conflict, NotFound
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
    text = render_server_config(
        {
            "private_key": ctx.secrets.decrypt(row["private_key_enc"]),
            "address": row["address"],
            "listen_port": row["listen_port"],
            "dns": row["dns"],
            "mtu": row["mtu"],
            "post_up": row["post_up"],
            "post_down": row["post_down"],
            "public_endpoint": row["public_endpoint"],
        },
        rendered_peers,
    )
    write_config_atomic(conf_path(ctx, row["name"]), text)
    return text


async def apply(ctx: AppContext, db: aiosqlite.Connection, row: dict[str, Any], restart: bool = False) -> None:
    """Re-render the config and push it to the running interface when it is up."""
    name = row["name"]
    active = await ctx.backend.is_active(name)
    if restart and active:
        await ctx.backend.down(name)
        await render(ctx, db, row)
        if row["enabled"]:
            await ctx.backend.up(name)
        return
    await render(ctx, db, row)
    if active:
        await ctx.backend.sync(name)


async def list_interfaces(ctx: AppContext) -> list[dict[str, Any]]:
    async with connect(ctx.db_path) as db:
        rows = await repo.list_all(db)
        return [await to_response(ctx, db, r) for r in rows]


async def get_interface(ctx: AppContext, name: str) -> dict[str, Any]:
    async with connect(ctx.db_path) as db:
        return await to_response(ctx, db, await _require(db, name))


def _check_scripts(ctx: AppContext, post_up: str | None, post_down: str | None) -> None:
    if (post_up or post_down) and not ctx.settings.wg_allow_custom_scripts:
        raise BadRequest("Custom PostUp/PostDown scripts are disabled (WG_ALLOW_CUSTOM_SCRIPTS)", code="scripts_disabled")


async def create_interface(ctx: AppContext, actor: audit.Actor, data: InterfaceCreate) -> dict[str, Any]:
    _check_scripts(ctx, data.post_up, data.post_down)
    private_key, public_key = keys.generate_keypair()
    async with connect(ctx.db_path) as db:
        if await repo.get_by_name(db, data.name):
            raise Conflict("Interface name already exists")
        if await repo.port_in_use(db, data.listen_port):
            raise Conflict("Listen port already in use")
        now = now_iso()
        row = await repo.create(
            db,
            now,
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
        await render(ctx, db, row)
        if data.enabled:
            await ctx.backend.up(row["name"])
        await audit.add(db, actor, "interface.created", target=row["name"], details={"address": data.address, "listen_port": data.listen_port})
        return await to_response(ctx, db, row)


async def update_interface(ctx: AppContext, actor: audit.Actor, name: str, data: InterfaceUpdate) -> dict[str, Any]:
    changes = data.model_dump(exclude_unset=True)
    async with connect(ctx.db_path) as db:
        row = await _require(db, name)
        if "post_up" in changes or "post_down" in changes:
            _check_scripts(ctx, changes.get("post_up"), changes.get("post_down"))
        if "listen_port" in changes and changes["listen_port"] != row["listen_port"]:
            if await repo.port_in_use(db, changes["listen_port"], exclude_id=row["id"]):
                raise Conflict("Listen port already in use")
        enabled_change = changes.pop("enabled", None)
        effective = {k: v for k, v in changes.items() if row.get(k) != v}
        now = now_iso()
        if effective:
            await repo.update(db, row["id"], now, **effective)
        if enabled_change is not None and bool(row["enabled"]) != enabled_change:
            await repo.update(db, row["id"], now, enabled=enabled_change)
        row = await _require(db, name)
        needs_restart = bool(RESTART_FIELDS & effective.keys())
        await apply(ctx, db, row, restart=needs_restart)
        if enabled_change is not None:
            await _set_state(ctx, db, actor, row, enabled_change)
        if effective:
            await audit.add(db, actor, "interface.updated", target=name, details={"fields": sorted(effective)})
        return await to_response(ctx, db, row)


async def _set_state(ctx: AppContext, db: aiosqlite.Connection, actor: audit.Actor, row: dict[str, Any], up: bool) -> None:
    name = row["name"]
    active = await ctx.backend.is_active(name)
    if up and not active:
        await ctx.backend.up(name)
        await audit.add(db, actor, "interface.up", target=name)
    elif not up and active:
        await ctx.backend.down(name)
        await audit.add(db, actor, "interface.down", target=name)


async def set_interface_state(ctx: AppContext, actor: audit.Actor, name: str, up: bool) -> dict[str, Any]:
    async with connect(ctx.db_path) as db:
        row = await _require(db, name)
        if bool(row["enabled"]) != up:
            await repo.update(db, row["id"], now_iso(), enabled=up)
            row = await _require(db, name)
        await render(ctx, db, row)
        await _set_state(ctx, db, actor, row, up)
        return await to_response(ctx, db, row)


async def delete_interface(ctx: AppContext, actor: audit.Actor, name: str) -> None:
    async with connect(ctx.db_path) as db:
        row = await _require(db, name)
        if await ctx.backend.is_active(name):
            await ctx.backend.down(name)
        path = conf_path(ctx, name)
        if path.exists():
            path.unlink()
        peer_count = await peers_repo.count_for_interface(db, row["id"])
        await repo.delete(db, row["id"])
        await audit.add(db, actor, "interface.deleted", target=name, details={"peers": peer_count})


async def server_config_text(ctx: AppContext, name: str) -> str:
    async with connect(ctx.db_path) as db:
        row = await _require(db, name)
        return await render(ctx, db, row)


async def reconcile(ctx: AppContext) -> None:
    """Startup job: import legacy configs, render everything, bring enabled interfaces up."""
    from app.services import importer

    await importer.import_legacy_configs(ctx)
    async with connect(ctx.db_path) as db:
        for row in await repo.list_all(db):
            try:
                await render(ctx, db, row)
                active = await ctx.backend.is_active(row["name"])
                if row["enabled"] and not active:
                    await ctx.backend.up(row["name"])
                elif row["enabled"] and active:
                    await ctx.backend.sync(row["name"])
            except Exception:  # noqa: BLE001 - keep reconciling the others
                logger.exception("Reconcile failed for interface %s", row["name"])
