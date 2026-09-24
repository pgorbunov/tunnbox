"""Render and parse WireGuard `.conf` files.

Rendering takes plain dicts (interface + peers) with secrets already decrypted.
Parsing keeps v1 conventions: keys are lower-cased (`privatekey`, `allowedips`),
a `# PublicEndpoint = host` comment in the interface section and `# Name: x`
comments above peers are preserved.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

_INTERFACE_ORDER = ("privatekey", "address", "listenport", "dns", "mtu", "postup", "postdown")
_PEER_ORDER = ("publickey", "presharedkey", "allowedips", "endpoint", "persistentkeepalive")
_DISPLAY = {
    "privatekey": "PrivateKey",
    "publickey": "PublicKey",
    "presharedkey": "PresharedKey",
    "address": "Address",
    "listenport": "ListenPort",
    "dns": "DNS",
    "mtu": "MTU",
    "postup": "PostUp",
    "postdown": "PostDown",
    "predown": "PreDown",
    "preup": "PreUp",
    "allowedips": "AllowedIPs",
    "endpoint": "Endpoint",
    "persistentkeepalive": "PersistentKeepalive",
    "table": "Table",
    "fwmark": "FwMark",
    "saveconfig": "SaveConfig",
}


def _display_key(key: str) -> str:
    return _DISPLAY.get(key, key.title())


def _sanitize(value: Any) -> str:
    """Config values are single-line; strip newlines so a value can't inject sections."""
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def render_server_config(interface: dict[str, Any], peers: list[dict[str, Any]]) -> str:
    """Render a server config.

    `interface` keys: private_key, address, listen_port, dns?, mtu?, post_up?, post_down?, public_endpoint?
    `peers` entries: name, public_key, preshared_key?, allowed_ips, persistent_keepalive?
    Only pass enabled peers.
    """
    lines = ["[Interface]"]
    if interface.get("public_endpoint"):
        lines.append(f"# PublicEndpoint = {_sanitize(interface['public_endpoint'])}")
    lines.append(f"PrivateKey = {_sanitize(interface['private_key'])}")
    lines.append(f"Address = {_sanitize(interface['address'])}")
    lines.append(f"ListenPort = {int(interface['listen_port'])}")
    if interface.get("dns"):
        lines.append(f"DNS = {_sanitize(interface['dns'])}")
    if interface.get("mtu"):
        lines.append(f"MTU = {int(interface['mtu'])}")
    if interface.get("post_up"):
        lines.append(f"PostUp = {_sanitize(interface['post_up'])}")
    if interface.get("post_down"):
        lines.append(f"PostDown = {_sanitize(interface['post_down'])}")

    for peer in peers:
        lines.append("")
        lines.append("[Peer]")
        lines.append(f"# Name: {_sanitize(peer.get('name') or '')}")
        lines.append(f"PublicKey = {_sanitize(peer['public_key'])}")
        if peer.get("preshared_key"):
            lines.append(f"PresharedKey = {_sanitize(peer['preshared_key'])}")
        lines.append(f"AllowedIPs = {_sanitize(peer['allowed_ips'])}")
        keepalive = int(peer.get("persistent_keepalive") or 0)
        if keepalive > 0:
            lines.append(f"PersistentKeepalive = {keepalive}")
    return "\n".join(lines) + "\n"


def render_client_config(
    *,
    private_key: str,
    address: str,
    dns: str | None,
    mtu: int | None,
    server_public_key: str,
    preshared_key: str | None,
    allowed_ips: str,
    endpoint_host: str,
    endpoint_port: int,
    persistent_keepalive: int,
) -> str:
    """Render the client-side config per spec §2.8."""
    lines = ["[Interface]", f"PrivateKey = {_sanitize(private_key)}", f"Address = {_sanitize(address)}"]
    if dns:
        lines.append(f"DNS = {_sanitize(dns)}")
    if mtu:
        lines.append(f"MTU = {int(mtu)}")
    lines += ["", "[Peer]", f"PublicKey = {_sanitize(server_public_key)}"]
    if preshared_key:
        lines.append(f"PresharedKey = {_sanitize(preshared_key)}")
    lines.append(f"AllowedIPs = {_sanitize(allowed_ips)}")
    host = _sanitize(endpoint_host)
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    lines.append(f"Endpoint = {host}:{int(endpoint_port)}")
    if persistent_keepalive > 0:
        lines.append(f"PersistentKeepalive = {int(persistent_keepalive)}")
    return "\n".join(lines) + "\n"


def parse_config(text: str) -> dict[str, Any]:
    """Parse a `.conf` into `{"interface": {...}, "peers": [{...}]}` with lower-cased keys."""
    config: dict[str, Any] = {"interface": {}, "peers": []}
    section: str | None = None
    current: dict[str, str] = {}
    pending_name: str | None = None

    def flush() -> None:
        nonlocal current
        if section == "interface":
            config["interface"].update(current)
        elif section == "peer" and current:
            config["peers"].append(current)
        current = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            if body.lower().startswith("publicendpoint") and "=" in body and section != "peer":
                config["interface"]["public_endpoint"] = body.split("=", 1)[1].strip()
            elif body.lower().startswith("name:"):
                pending_name = body.split(":", 1)[1].strip()
                if section == "peer":
                    current["name"] = pending_name
            continue
        lowered = line.lower()
        if lowered == "[interface]":
            flush()
            section = "interface"
            continue
        if lowered == "[peer]":
            flush()
            section = "peer"
            if pending_name:
                current["name"] = pending_name
                pending_name = None
            continue
        if "=" in line and section:
            key, value = line.split("=", 1)
            current[key.strip().lower().replace(" ", "_")] = value.strip()
    flush()
    return config


def write_config_atomic(path: Path, content: str) -> None:
    """Write `content` to `path` via a temp file in the same directory, mode 0600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
