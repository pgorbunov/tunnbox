"""Backups (tar.gz of DB + rendered configs) and JSON export."""

from __future__ import annotations

import io
import json
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import aiosqlite

from app import __version__
from app.context import AppContext
from app.core.security import now_iso
from app.db.connection import connect, fetch_all
from app.db.repos import settings as settings_repo


async def _consistent_db_copy(ctx: AppContext, target: Path) -> None:
    async with aiosqlite.connect(str(ctx.db_path)) as source:
        async with aiosqlite.connect(str(target)) as dest:
            await source.backup(dest)


async def build_backup(ctx: AppContext) -> bytes:
    """tar.gz containing `tunnbox.db` and `wireguard/<name>.conf` files."""
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        db_copy = Path(tmp) / "tunnbox.db"
        await _consistent_db_copy(ctx, db_copy)
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            tar.add(str(db_copy), arcname="tunnbox.db")
            config_dir = ctx.settings.config_dir
            if config_dir.is_dir():
                for conf in sorted(config_dir.glob("*.conf")):
                    tar.add(str(conf), arcname=f"wireguard/{conf.name}")
    return buffer.getvalue()


async def build_export(ctx: AppContext, exported_by: str) -> dict[str, Any]:
    """Secret-free JSON export of users, interfaces, peers, settings and audit."""
    async with connect(ctx.db_path) as db:
        users = await fetch_all(db, "SELECT id, username, role, is_active, totp_enabled, last_login_at, created_at FROM users ORDER BY id")
        interfaces = await fetch_all(
            db,
            "SELECT id, name, public_key, address, listen_port, dns, mtu, post_up, post_down, public_endpoint, enabled, created_at, updated_at FROM interfaces ORDER BY id",
        )
        peers = await fetch_all(
            db,
            """SELECT p.id, p.interface_id, i.name AS interface_name, p.name, p.public_key, p.allowed_ips, p.client_allowed_ips,
                      p.client_dns, p.persistent_keepalive, p.enabled, p.expires_at, p.notes, p.created_at, p.updated_at,
                      p.last_handshake_at, p.rx_total, p.tx_total
               FROM peers p JOIN interfaces i ON i.id = p.interface_id ORDER BY p.id""",
        )
        settings = await settings_repo.get_all(db)
        audit = await fetch_all(db, "SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10000")
    for entry in audit:
        if entry.get("details"):
            try:
                entry["details"] = json.loads(entry["details"])
            except ValueError:
                pass
    for row in users + interfaces + peers:
        for key in ("is_active", "totp_enabled", "enabled"):
            if key in row:
                row[key] = bool(row[key])
    return {
        "metadata": {"exported_at": now_iso(), "version": __version__, "exported_by": exported_by},
        "users": users,
        "interfaces": interfaces,
        "peers": peers,
        "settings": settings,
        "audit_logs": audit,
    }
