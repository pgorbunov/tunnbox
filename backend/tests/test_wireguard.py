"""Key generation, config rendering/parsing, mock backend and dump parsing."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

from app.core.crypto import SecretBox
from app.services.wireguard import keys
from app.services.wireguard.mock import MockBackend
from app.services.wireguard.real import parse_dump
from app.services.wireguard.renderer import parse_config, render_server_config, write_config_atomic


def test_x25519_matches_rfc7748_vector() -> None:
    private = bytes.fromhex("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a")
    public = bytes.fromhex("8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a")
    assert keys.public_key_from_private(base64.b64encode(private).decode()) == base64.b64encode(public).decode()


def test_generated_keys_are_clamped_and_valid() -> None:
    private, public = keys.generate_keypair()
    raw = base64.b64decode(private)
    assert len(raw) == 32 and raw[0] & 7 == 0 and raw[31] & 128 == 0 and raw[31] & 64 == 64
    assert keys.is_valid_key(public) and keys.is_valid_key(keys.generate_preshared_key())
    assert not keys.is_valid_key("short") and not keys.is_valid_key("!" * 44)


def test_render_and_parse_roundtrip(tmp_path: Path) -> None:
    text = render_server_config(
        {"private_key": "PRIV", "address": "10.8.0.1/24", "listen_port": 51820, "dns": "1.1.1.1", "mtu": None, "post_up": None, "post_down": None, "public_endpoint": "vpn.example.com"},
        [{"name": "laptop\ninjected", "public_key": "PUB", "preshared_key": "PSK", "allowed_ips": "10.8.0.2/32", "persistent_keepalive": 25}],
    )
    assert "\ninjected" not in text and "# Name: laptop injected" in text
    parsed = parse_config(text)
    assert parsed["interface"]["privatekey"] == "PRIV" and parsed["interface"]["public_endpoint"] == "vpn.example.com"
    assert parsed["peers"] == [{"name": "laptop injected", "publickey": "PUB", "presharedkey": "PSK", "allowedips": "10.8.0.2/32", "persistentkeepalive": "25"}]
    path = tmp_path / "wg0.conf"
    write_config_atomic(path, text)
    assert path.read_text() == text and oct(path.stat().st_mode & 0o777) == "0o600"
    assert not list(tmp_path.glob(".wg0.conf.*"))


def test_parse_v1_config_with_endpoint_comment() -> None:
    parsed = parse_config("""[Interface]
# PublicEndpoint = 203.0.113.9
PrivateKey = abc
Address = 10.0.0.1/24
ListenPort = 51820

[Peer]
PublicKey = p1
AllowedIPs = 10.0.0.2/32
Endpoint = 192.168.1.100:51820
""")
    assert parsed["interface"]["public_endpoint"] == "203.0.113.9"
    assert parsed["peers"][0]["endpoint"] == "192.168.1.100:51820"


def test_parse_wg_dump() -> None:
    dump = parse_dump("PRIV\tSERVERPUB\t51820\toff\nPEER1\tPSK\t1.2.3.4:5555\t10.8.0.2/32\t1700000000\t1024\t2048\t25\nPEER2\t(none)\t(none)\t10.8.0.3/32\t0\t0\t0\toff\n")
    assert dump.listen_port == 51820 and dump.public_key == "SERVERPUB" and len(dump.peers) == 2
    p1, p2 = dump.peers
    assert p1.preshared and p1.endpoint == "1.2.3.4:5555" and p1.rx == 1024 and p1.tx == 2048 and p1.keepalive == 25
    assert p1.latest_handshake == datetime.fromtimestamp(1700000000, tz=timezone.utc)
    assert not p2.preshared and p2.endpoint is None and p2.latest_handshake is None


async def test_mock_backend_stats_grow(tmp_path: Path) -> None:
    backend = MockBackend(tmp_path)
    conf = render_server_config(
        {"private_key": "PRIV", "address": "10.8.0.1/24", "listen_port": 51820},
        [{"name": f"p{i}", "public_key": f"PUB{i}", "allowed_ips": f"10.8.0.{i + 2}/32", "persistent_keepalive": 25} for i in range(20)],
    )
    (tmp_path / "wg0.conf").write_text(conf)
    assert not await backend.is_active("wg0")
    await backend.up("wg0")
    assert await backend.is_active("wg0")
    first = await backend.dump("wg0")
    assert first.listen_port == 51820 and len(first.peers) == 20
    online = [p for p in first.peers if p.latest_handshake]
    assert 3 <= len(online) <= 17
    second = await backend.dump("wg0")
    assert all(b.rx >= a.rx and b.tx >= a.tx for a, b in zip(first.peers, second.peers, strict=True))
    await backend.down("wg0")
    assert not await backend.is_active("wg0")


def test_secretbox_v1_compatibility() -> None:
    box = SecretBox("secret-key")
    token = box.encrypt("hello")
    assert ":" in token and box.decrypt(token) == "hello"
    assert SecretBox("secret-key").decrypt(token) == "hello"
    # legacy static-salt format (no colon)
    import base64 as b64

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    key = b64.urlsafe_b64encode(PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"wg-ui-static-salt", iterations=100_000).derive(b"secret-key"))
    legacy = Fernet(key).encrypt(b"old-value").decode()
    assert box.decrypt(legacy) == "old-value"
    import pytest

    from app.core.crypto import DecryptionError

    with pytest.raises(DecryptionError):
        SecretBox("other").decrypt(token)
