"""Real backend driving `wg`, `wg-quick` and `ip` via exec lists (never a shell)."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import BackendError
from app.schemas.common import validate_interface_name
from app.services.wireguard.base import InterfaceDump, PeerDump

logger = logging.getLogger(__name__)

_IGNORABLE_UP = ("already exists",)
_IGNORABLE_DOWN = ("is not a wireguard interface", "does not exist", "cannot find device")


async def run(*args: str, stdin: bytes | None = None, timeout: float = 30) -> tuple[int, str, str]:
    """Run a command; returns (rc, stdout, stderr). Raises BackendError if the binary is missing."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(stdin), timeout=timeout)
    except FileNotFoundError as exc:
        raise BackendError(f"Command not found: {args[0]}") from exc
    except asyncio.TimeoutError as exc:
        raise BackendError(f"Command timed out: {args[0]}") from exc
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


class RealBackend:
    mode = "real"

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def conf_path(self, name: str) -> Path:
        validate_interface_name(name)
        return self.config_dir / f"{name}.conf"

    async def is_active(self, name: str) -> bool:
        validate_interface_name(name)
        rc, _, _ = await run("ip", "link", "show", name)
        return rc == 0

    async def up(self, name: str) -> None:
        rc, _, err = await run("wg-quick", "up", str(self.conf_path(name)))
        if rc != 0 and not any(marker in err.lower() for marker in _IGNORABLE_UP):
            raise BackendError(f"wg-quick up {name} failed: {err.strip()[:500]}")

    async def down(self, name: str) -> None:
        rc, _, err = await run("wg-quick", "down", str(self.conf_path(name)))
        if rc != 0 and not any(marker in err.lower() for marker in _IGNORABLE_DOWN):
            raise BackendError(f"wg-quick down {name} failed: {err.strip()[:500]}")

    async def sync(self, name: str) -> None:
        rc, stripped, err = await run("wg-quick", "strip", str(self.conf_path(name)))
        if rc != 0:
            raise BackendError(f"wg-quick strip {name} failed: {err.strip()[:500]}")
        fd, tmp = tempfile.mkstemp(prefix=f".{name}.sync.", suffix=".conf")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(stripped)
            os.chmod(tmp, 0o600)
            rc, _, err = await run("wg", "syncconf", name, tmp)
            if rc != 0:
                raise BackendError(f"wg syncconf {name} failed: {err.strip()[:500]}")
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    async def dump(self, name: str) -> InterfaceDump:
        validate_interface_name(name)
        rc, out, err = await run("wg", "show", name, "dump")
        if rc != 0:
            raise BackendError(f"wg show {name} failed: {err.strip()[:500]}")
        return parse_dump(out)

    async def version(self) -> str | None:
        try:
            rc, out, _ = await run("wg", "--version")
        except BackendError:
            return None
        return out.strip().splitlines()[0] if rc == 0 and out.strip() else None

    async def kernel_module(self) -> bool:
        try:
            return Path("/sys/module/wireguard").exists()
        except OSError:
            return False


def parse_dump(text: str) -> InterfaceDump:
    """Parse `wg show <iface> dump` (tab separated)."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return InterfaceDump(listen_port=0, public_key="")
    head = lines[0].split("\t")
    # private_key, public_key, listen_port, fwmark
    listen_port = int(head[2]) if len(head) > 2 and head[2].isdigit() else 0
    dump = InterfaceDump(listen_port=listen_port, public_key=head[1] if len(head) > 1 else "")
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) < 8:
            continue
        # public_key, preshared_key, endpoint, allowed_ips, latest_handshake, rx, tx, keepalive
        handshake = int(cols[4]) if cols[4].isdigit() else 0
        keepalive = int(cols[7]) if cols[7].isdigit() else 0
        dump.peers.append(
            PeerDump(
                public_key=cols[0],
                preshared=cols[1] not in ("", "(none)"),
                endpoint=None if cols[2] in ("", "(none)") else cols[2],
                allowed_ips=cols[3].replace(",", ", ") if cols[3] != "(none)" else "",
                latest_handshake=datetime.fromtimestamp(handshake, tz=timezone.utc) if handshake > 0 else None,
                rx=int(cols[5]) if cols[5].isdigit() else 0,
                tx=int(cols[6]) if cols[6].isdigit() else 0,
                keepalive=keepalive,
            )
        )
    return dump
