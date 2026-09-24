"""One-time import of v1 `.conf` files (and `peer_metadata`) into the database.

Safety rules:
- each file is imported inside a SAVEPOINT and rolled back as a unit on error;
- the original file is copied to `<name>.conf.v1.bak` (0600) before we ever
  re-render it;
- files that use directives the renderer cannot reproduce (Table, FwMark,
  PreUp, PreDown, SaveConfig, peer Endpoint) are skipped with a warning
  instead of being silently rewritten without them;
- `peer_metadata` is dropped only once every file has imported cleanly.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

import aiosqlite

from app.context import AppContext
from app.core.crypto import DecryptionError
from app.core.security import now_iso
from app.db.connection import connect, fetch_all, fetch_value
from app.db.repos import interfaces as interfaces_repo
from app.db.repos import peers as peers_repo
from app.schemas.common import validate_interface_name
from app.services.wireguard import keys
from app.services.wireguard.renderer import parse_config

logger = logging.getLogger(__name__)

UNSUPPORTED_INTERFACE_KEYS = {"table", "fwmark", "preup", "predown", "saveconfig"}
UNSUPPORTED_PEER_KEYS = {"endpoint"}


class SkipFile(Exception):
    """The file is left untouched; the reason is logged."""


async def _legacy_metadata(db: aiosqlite.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    exists = await fetch_value(db, "SELECT 1 FROM sqlite_master WHERE type='table' AND name='peer_metadata'")
    if not exists:
        return {}
    rows = await fetch_all(db, "SELECT interface_name, public_key, name, private_key FROM peer_metadata")
    return {(r["interface_name"], r["public_key"]): r for r in rows}


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def _backup(path: Path) -> None:
    backup = path.with_name(path.name + ".v1.bak")
    if backup.exists():
        return
    shutil.copy2(path, backup)
    os.chmod(backup, 0o600)


async def import_legacy_configs(ctx: AppContext) -> int:
    """Import every `<name>.conf` not yet in the DB. Idempotent; never overwrites rows."""
    config_dir = ctx.settings.config_dir
    if not config_dir.is_dir():
        return 0
    imported = 0
    all_clean = True
    async with connect(ctx.db_path, immediate=True) as db:
        metadata = await _legacy_metadata(db)
        for path in sorted(config_dir.glob("*.conf")):
            name = path.stem
            try:
                validate_interface_name(name)
            except ValueError:
                logger.warning("Skipping config with invalid interface name: %s", path.name)
                all_clean = False
                continue
            if await interfaces_repo.get_by_name(db, name):
                continue
            await db.execute("SAVEPOINT import_file")
            try:
                text = path.read_text(encoding="utf-8")
                await _import_one(ctx, db, name, text, metadata)
                _backup(path)
                await db.execute("RELEASE SAVEPOINT import_file")
                imported += 1
            except SkipFile as exc:
                await db.execute("ROLLBACK TO SAVEPOINT import_file")
                await db.execute("RELEASE SAVEPOINT import_file")
                logger.warning("Not importing %s: %s (file left untouched)", path.name, exc)
                all_clean = False
            except Exception:  # noqa: BLE001 - one bad file must not block startup
                await db.execute("ROLLBACK TO SAVEPOINT import_file")
                await db.execute("RELEASE SAVEPOINT import_file")
                logger.exception("Failed to import %s (rolled back, file left untouched)", path.name)
                all_clean = False
        if metadata and all_clean:
            await db.execute("DROP TABLE IF EXISTS peer_metadata")
    return imported


async def _import_one(
    ctx: AppContext,
    db: aiosqlite.Connection,
    name: str,
    text: str,
    metadata: dict[tuple[str, str], dict[str, Any]],
) -> None:
    parsed = parse_config(text)
    iface = parsed["interface"]
    unsupported = sorted(UNSUPPORTED_INTERFACE_KEYS & set(iface))
    if unsupported:
        raise SkipFile(f"unsupported [Interface] keys {unsupported}")
    private_key = iface.get("privatekey", "")
    if not keys.is_valid_key(private_key) or not iface.get("address"):
        raise SkipFile("missing or invalid PrivateKey/Address")
    listen_port = _int_or_none(iface.get("listenport")) or 51820
    if await interfaces_repo.port_in_use(db, listen_port):
        raise SkipFile(f"listen port {listen_port} already in use")
    for index, peer in enumerate(parsed["peers"], start=1):
        bad = sorted(UNSUPPORTED_PEER_KEYS & set(peer))
        if bad:
            raise SkipFile(f"peer #{index} uses unsupported keys {bad}")
        if not keys.is_valid_key(peer.get("publickey", "")) or not peer.get("allowedips"):
            raise SkipFile(f"peer #{index} has an invalid PublicKey or no AllowedIPs")

    now = now_iso()
    row = await interfaces_repo.create(
        db,
        now,
        name=name,
        private_key_enc=ctx.secrets.encrypt(private_key),
        public_key=keys.public_key_from_private(private_key),
        address=iface["address"],
        listen_port=listen_port,
        dns=iface.get("dns") or None,
        mtu=_int_or_none(iface.get("mtu")),
        post_up=iface.get("postup") or None,
        post_down=iface.get("postdown") or None,
        public_endpoint=iface.get("public_endpoint") or None,
        enabled=True,
    )
    for index, peer in enumerate(parsed["peers"], start=1):
        public_key = peer["publickey"]
        meta = metadata.get((name, public_key), {})
        private_enc = None
        if meta.get("private_key"):
            try:
                private_enc = ctx.secrets.encrypt(ctx.secrets.decrypt(meta["private_key"]))
            except DecryptionError:
                logger.warning("Could not decrypt legacy private key for peer %s on %s", public_key[:8], name)
        psk = peer.get("presharedkey")
        await peers_repo.create(
            db,
            now,
            interface_id=row["id"],
            name=peer.get("name") or meta.get("name") or f"peer-{index}",
            public_key=public_key,
            private_key_enc=private_enc,
            preshared_key_enc=ctx.secrets.encrypt(psk) if psk and keys.is_valid_key(psk) else None,
            allowed_ips=peer["allowedips"],
            client_allowed_ips="0.0.0.0/0, ::/0",
            persistent_keepalive=_int_or_none(peer.get("persistentkeepalive")) or 0,
            enabled=True,
        )
    logger.info("Imported legacy interface %s with %d peers", name, len(parsed["peers"]))
