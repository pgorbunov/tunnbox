"""Peer management: CRUD, IP assignment, client config, QR, bulk actions, expiry."""

from __future__ import annotations

import io
import ipaddress
import logging
from datetime import timedelta
from typing import Any

import aiosqlite
import qrcode

from app.context import AppContext
from app.core.errors import Conflict, NotFound
from app.core.security import iso, now_iso, parse_iso, utcnow
from app.db.connection import connect
from app.db.repos import interfaces as interfaces_repo
from app.db.repos import peers as repo
from app.db.repos import settings as settings_repo
from app.schemas.peers import PeerCreate, PeerUpdate
from app.services import audit
from app.services import interfaces as interfaces_service
from app.services.wireguard import keys
from app.services.wireguard.renderer import render_client_config

logger = logging.getLogger(__name__)

ONLINE_WINDOW = timedelta(seconds=180)


def _status(row: dict[str, Any], is_online: bool, now_ts: str) -> str:
    if row["expires_at"] and row["expires_at"] <= now_ts:
        return "expired"
    if not row["enabled"]:
        return "disabled"
    return "online" if is_online else "offline"


def to_response(ctx: AppContext, row: dict[str, Any]) -> dict[str, Any]:
    now = utcnow()
    handshake = parse_iso(row["last_handshake_at"])
    is_online = bool(row["enabled"]) and handshake is not None and (now - handshake) <= ONLINE_WINDOW
    return {
        "id": row["id"],
        "interface_id": row["interface_id"],
        "interface_name": row["interface_name"],
        "name": row["name"],
        "public_key": row["public_key"],
        "allowed_ips": row["allowed_ips"],
        "client_allowed_ips": row["client_allowed_ips"],
        "client_dns": row["client_dns"],
        "persistent_keepalive": row["persistent_keepalive"],
        "enabled": bool(row["enabled"]),
        "expires_at": row["expires_at"],
        "notes": row["notes"],
        "has_private_key": bool(row["private_key_enc"]),
        "has_preshared_key": bool(row["preshared_key_enc"]),
        "endpoint": ctx.live.endpoints.get(row["id"]),
        "latest_handshake_at": row["last_handshake_at"],
        "is_online": is_online,
        "rx_total": row["rx_total"],
        "tx_total": row["tx_total"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": _status(row, is_online, iso(now)),
    }


async def _require(db: aiosqlite.Connection, peer_id: int) -> dict[str, Any]:
    row = await repo.get(db, peer_id)
    if row is None:
        raise NotFound("Peer not found")
    return row


async def _require_interface(db: aiosqlite.Connection, name: str) -> dict[str, Any]:
    row = await interfaces_repo.get_by_name(db, name)
    if row is None:
        raise NotFound("Interface not found")
    return row


# --- IP assignment --------------------------------------------------------------


def _hosts_in(cidrs: str) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    out: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for part in cidrs.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(ipaddress.ip_interface(part).ip)
        except ValueError:
            continue
    return out


def compute_next_ip(interface_address: str, taken: set[Any]) -> str:
    """First free host in each of the interface's networks, as /32 and /128 entries."""
    results: list[str] = []
    for part in interface_address.split(","):
        part = part.strip()
        if not part:
            continue
        iface = ipaddress.ip_interface(part)
        network = iface.network
        limit = 65536  # never scan a huge IPv6 range end to end
        for index, host in enumerate(network.hosts()):
            if index >= limit:
                break
            if host == iface.ip or host in taken:
                continue
            results.append(f"{host}/{host.max_prefixlen}")
            taken.add(host)
            break
        else:
            raise Conflict(f"No free addresses left in {network}")
    if not results:
        raise Conflict("Interface has no usable address range")
    return ", ".join(results)


async def _taken_hosts(db: aiosqlite.Connection, iface: dict[str, Any], exclude_peer_id: int | None = None) -> set[Any]:
    taken = _hosts_in(iface["address"])
    for peer in await repo.list_for_interface(db, iface["id"]):
        if peer["id"] != exclude_peer_id:
            taken |= _hosts_in(peer["allowed_ips"])
    return taken


async def next_ip(ctx: AppContext, interface_name: str) -> str:
    async with connect(ctx.db_path) as db:
        iface = await _require_interface(db, interface_name)
        return compute_next_ip(iface["address"], await _taken_hosts(db, iface))


def _check_free(allowed_ips: str, taken: set[Any]) -> None:
    clash = _hosts_in(allowed_ips) & taken
    if clash:
        raise Conflict(f"Address already in use: {', '.join(str(ip) for ip in sorted(clash, key=str))}")


# --- CRUD -----------------------------------------------------------------------


async def list_for_interface(ctx: AppContext, interface_name: str, *, q: str | None, status: str | None, sort: str, order: str) -> list[dict[str, Any]]:
    async with connect(ctx.db_path) as db:
        iface = await _require_interface(db, interface_name)
        rows = await repo.list_for_interface(db, iface["id"], q=q, sort=sort, order=order)
    peers = [to_response(ctx, r) for r in rows]
    return [p for p in peers if not status or p["status"] == status]


async def search(ctx: AppContext, *, q: str | None, interface: str | None, status: str | None, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    async with connect(ctx.db_path) as db:
        rows = await repo.list_all(db, q=q, interface=interface)
    peers = [to_response(ctx, r) for r in rows]
    if status:
        peers = [p for p in peers if p["status"] == status]
    start = (page - 1) * page_size
    return peers[start : start + page_size], len(peers)


async def get_peer(ctx: AppContext, peer_id: int) -> dict[str, Any]:
    async with connect(ctx.db_path) as db:
        return to_response(ctx, await _require(db, peer_id))


async def create_peer(ctx: AppContext, actor: audit.Actor, interface_name: str, data: PeerCreate) -> dict[str, Any]:
    private_key, public_key = keys.generate_keypair()
    psk = keys.generate_preshared_key()
    async with connect(ctx.db_path) as db:
        iface = await _require_interface(db, interface_name)
        defaults = await settings_repo.get_all(db)
        taken = await _taken_hosts(db, iface)
        if data.allowed_ips:
            _check_free(data.allowed_ips, taken)
            allowed_ips = data.allowed_ips
        else:
            allowed_ips = compute_next_ip(iface["address"], taken)
        keepalive = data.persistent_keepalive if data.persistent_keepalive is not None else int(defaults["default_keepalive"])
        row = await repo.create(
            db,
            now_iso(),
            interface_id=iface["id"],
            name=data.name,
            public_key=public_key,
            private_key_enc=ctx.secrets.encrypt(private_key),
            preshared_key_enc=ctx.secrets.encrypt(psk),
            allowed_ips=allowed_ips,
            client_allowed_ips=data.client_allowed_ips or defaults["default_client_allowed_ips"],
            client_dns=data.client_dns,
            persistent_keepalive=keepalive,
            enabled=data.enabled,
            expires_at=data.expires_at,
            notes=data.notes,
        )
        await interfaces_service.apply(ctx, db, iface)
        await audit.add(db, actor, "peer.created", target=f"{interface_name}/{row['name']}", details={"peer_id": row["id"], "allowed_ips": allowed_ips})
        return to_response(ctx, row)


async def update_peer(ctx: AppContext, actor: audit.Actor, peer_id: int, data: PeerUpdate) -> dict[str, Any]:
    changes = data.model_dump(exclude_unset=True)
    async with connect(ctx.db_path) as db:
        row = await _require(db, peer_id)
        iface = await interfaces_repo.get(db, row["interface_id"])
        assert iface is not None
        if "allowed_ips" in changes and changes["allowed_ips"] != row["allowed_ips"]:
            _check_free(changes["allowed_ips"], await _taken_hosts(db, iface, exclude_peer_id=peer_id))
        enabled_change = changes.get("enabled")
        effective = {k: v for k, v in changes.items() if row.get(k) != v and not (k == "enabled" and bool(row["enabled"]) == v)}
        if effective:
            await repo.update(db, peer_id, now_iso(), **effective)
            row = await _require(db, peer_id)
            await interfaces_service.apply(ctx, db, iface)
            action = "peer.updated"
            if list(effective) == ["enabled"]:
                action = "peer.enabled" if enabled_change else "peer.disabled"
            await audit.add(db, actor, action, target=f"{row['interface_name']}/{row['name']}", details={"peer_id": peer_id, "fields": sorted(effective)})
        return to_response(ctx, row)


async def set_enabled(ctx: AppContext, actor: audit.Actor, peer_id: int, enabled: bool) -> dict[str, Any]:
    return await update_peer(ctx, actor, peer_id, PeerUpdate(enabled=enabled))


async def delete_peer(ctx: AppContext, actor: audit.Actor, peer_id: int) -> None:
    async with connect(ctx.db_path) as db:
        row = await _require(db, peer_id)
        iface = await interfaces_repo.get(db, row["interface_id"])
        assert iface is not None
        await repo.delete(db, peer_id)
        await interfaces_service.apply(ctx, db, iface)
        await audit.add(db, actor, "peer.deleted", target=f"{row['interface_name']}/{row['name']}", details={"peer_id": peer_id})
    ctx.live.endpoints.pop(peer_id, None)
    ctx.live.raw_counters.pop(peer_id, None)


async def rotate_keys(ctx: AppContext, actor: audit.Actor, peer_id: int) -> dict[str, Any]:
    private_key, public_key = keys.generate_keypair()
    psk = keys.generate_preshared_key()
    async with connect(ctx.db_path) as db:
        row = await _require(db, peer_id)
        iface = await interfaces_repo.get(db, row["interface_id"])
        assert iface is not None
        await repo.update(
            db, peer_id, now_iso(),
            public_key=public_key,
            private_key_enc=ctx.secrets.encrypt(private_key),
            preshared_key_enc=ctx.secrets.encrypt(psk),
            last_handshake_at=None,
        )
        row = await _require(db, peer_id)
        await interfaces_service.apply(ctx, db, iface)
        await audit.add(db, actor, "peer.keys_rotated", target=f"{row['interface_name']}/{row['name']}", details={"peer_id": peer_id})
    ctx.live.raw_counters.pop(peer_id, None)
    ctx.live.endpoints.pop(peer_id, None)
    return to_response(ctx, row)


async def bulk(ctx: AppContext, actor: audit.Actor, ids: list[int], action: str) -> int:
    affected = 0
    async with connect(ctx.db_path) as db:
        rows = await repo.list_by_ids(db, ids)
        touched_interfaces: dict[int, dict[str, Any]] = {}
        for row in rows:
            if action == "delete":
                await repo.delete(db, row["id"])
                await audit.add(db, actor, "peer.deleted", target=f"{row['interface_name']}/{row['name']}", details={"peer_id": row["id"], "bulk": True})
            else:
                enabled = action == "enable"
                if bool(row["enabled"]) == enabled:
                    continue
                await repo.update(db, row["id"], now_iso(), enabled=enabled)
                await audit.add(db, actor, f"peer.{action}d", target=f"{row['interface_name']}/{row['name']}", details={"peer_id": row["id"], "bulk": True})
            affected += 1
            if row["interface_id"] not in touched_interfaces:
                iface = await interfaces_repo.get(db, row["interface_id"])
                if iface:
                    touched_interfaces[row["interface_id"]] = iface
        for iface in touched_interfaces.values():
            await interfaces_service.apply(ctx, db, iface)
    return affected


# --- client config ---------------------------------------------------------------


async def client_config(ctx: AppContext, peer_id: int, allowed_ips_override: str | None = None, *, actor: audit.Actor | None = None) -> tuple[str, dict[str, Any]]:
    """Render the client config; returns (text, peer_row). 404 when no private key is stored."""
    async with connect(ctx.db_path) as db:
        row = await _require(db, peer_id)
        if not row["private_key_enc"]:
            raise NotFound("No private key stored for this peer")
        iface = await interfaces_repo.get(db, row["interface_id"])
        assert iface is not None
        defaults = await settings_repo.get_all(db)
        endpoint_host = iface["public_endpoint"] or defaults["public_endpoint"] or "SERVER_ENDPOINT"
        text = render_client_config(
            private_key=ctx.secrets.decrypt(row["private_key_enc"]),
            address=row["allowed_ips"],
            dns=row["client_dns"] or iface["dns"] or defaults["default_dns"] or None,
            mtu=iface["mtu"] or defaults["default_mtu"],
            server_public_key=iface["public_key"],
            preshared_key=ctx.secrets.decrypt(row["preshared_key_enc"]) if row["preshared_key_enc"] else None,
            allowed_ips=allowed_ips_override or row["client_allowed_ips"],
            endpoint_host=endpoint_host,
            endpoint_port=iface["listen_port"],
            persistent_keepalive=row["persistent_keepalive"],
        )
        if actor is not None:
            await audit.add(db, actor, "peer.config_downloaded", target=f"{row['interface_name']}/{row['name']}", details={"peer_id": peer_id})
        return text, row


def qr_png(text: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# --- background job ---------------------------------------------------------------


async def expire_peers(ctx: AppContext) -> int:
    """Disable enabled peers whose `expires_at` has passed; re-render affected interfaces."""
    now = now_iso()
    disabled = 0
    async with connect(ctx.db_path) as db:
        rows = await repo.expired_enabled(db, now)
        touched: dict[int, dict[str, Any]] = {}
        for row in rows:
            await repo.update(db, row["id"], now, enabled=False)
            await audit.add(db, audit.Actor.system(), "peer.auto_disabled", target=f"{row['interface_name']}/{row['name']}", details={"peer_id": row["id"], "expires_at": row["expires_at"]})
            disabled += 1
            if row["interface_id"] not in touched:
                iface = await interfaces_repo.get(db, row["interface_id"])
                if iface:
                    touched[row["interface_id"]] = iface
        for iface in touched.values():
            await interfaces_service.apply(ctx, db, iface)
    return disabled
