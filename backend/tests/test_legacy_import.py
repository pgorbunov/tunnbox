"""Upgrade path: v1 database + `.conf` files are imported once, idempotently."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import bcrypt
from httpx import ASGITransport, AsyncClient

from app.core.crypto import SecretBox
from app.main import create_app
from app.services.wireguard import keys
from tests.conftest import do_login, make_env

SECRET = "test-secret-key-do-not-use"


def _make_v1(tmp_path: Path) -> tuple[str, str]:
    db = sqlite3.connect(tmp_path / "tunnbox.db")
    db.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL,
                            is_admin BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE peer_metadata (id INTEGER PRIMARY KEY AUTOINCREMENT, interface_name TEXT NOT NULL, public_key TEXT NOT NULL,
                                    name TEXT NOT NULL, private_key TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    UNIQUE(interface_name, public_key));
        CREATE TABLE audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL, details TEXT,
                                 ip_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE refresh_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, token TEXT UNIQUE NOT NULL,
                                     expires_at TIMESTAMP NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        """
    )
    pw_hash = bcrypt.hashpw(b"legacy-password-1", bcrypt.gensalt(rounds=4)).decode()
    db.execute("INSERT INTO users (username, hashed_password, is_admin) VALUES ('legacy', ?, 1)", (pw_hash,))
    db.execute("INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES (1, 'x', '2030-01-01')")
    db.execute("INSERT INTO settings (key, value) VALUES ('public_endpoint', 'old.example.com')")
    db.execute("INSERT INTO settings (key, value) VALUES ('wg_default_dns', '8.8.8.8')")
    server_priv, _ = keys.generate_keypair()
    peer_priv, peer_pub = keys.generate_keypair()
    _, peer2_pub = keys.generate_keypair()
    box = SecretBox(SECRET)
    db.execute(
        "INSERT INTO peer_metadata (interface_name, public_key, name, private_key) VALUES ('wg0', ?, 'alice-laptop', ?)",
        (peer_pub, box.encrypt(peer_priv)),
    )
    db.commit()
    db.close()
    wg = tmp_path / "wireguard"
    wg.mkdir()
    (wg / "wg0.conf").write_text(
        f"""[Interface]
# PublicEndpoint = 203.0.113.5
PrivateKey = {server_priv}
Address = 10.0.0.1/24
ListenPort = 51820
DNS = 1.1.1.1
PostUp = iptables -A FORWARD -i %i -j ACCEPT

[Peer]
PublicKey = {peer_pub}
AllowedIPs = 10.0.0.2/32
PersistentKeepalive = 25

[Peer]
PublicKey = {peer2_pub}
AllowedIPs = 10.0.0.3/32
"""
    )
    (wg / "broken.conf").write_text("garbage\n")
    return peer_pub, peer2_pub


async def test_legacy_import(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    peer_pub, peer2_pub = _make_v1(tmp_path)
    make_env(tmp_path, monkeypatch, SECRET_KEY=SECRET)
    for _ in range(2):  # second startup must be a no-op
        app = create_app()
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                assert (await client.get("/api/auth/status")).json()["setup_required"] is False
                admin = await do_login(client, "legacy", "legacy-password-1")
                assert admin.user["role"] == "admin"
                interfaces = (await admin.get("/api/interfaces")).json()
                assert [i["name"] for i in interfaces] == ["wg0"]
                iface = interfaces[0]
                assert iface["listen_port"] == 51820 and iface["public_endpoint"] == "203.0.113.5" and iface["dns"] == "1.1.1.1"
                assert iface["post_up"] == "iptables -A FORWARD -i %i -j ACCEPT" and iface["peer_count"] == 2
                peers = (await admin.get("/api/interfaces/wg0/peers")).json()
                by_key = {p["public_key"]: p for p in peers}
                assert by_key[peer_pub]["name"] == "alice-laptop" and by_key[peer_pub]["has_private_key"]
                assert by_key[peer2_pub]["name"] == "peer-2" and not by_key[peer2_pub]["has_private_key"]
                config = await admin.get(f"/api/peers/{by_key[peer_pub]['id']}/config")
                assert config.status_code == 200 and "Endpoint = 203.0.113.5:51820" in config.text
                assert (await admin.get(f"/api/peers/{by_key[peer2_pub]['id']}/config")).status_code == 404
                settings = (await admin.get("/api/settings")).json()
                assert settings["public_endpoint"] == "old.example.com" and settings["default_dns"] == "8.8.8.8"
                rendered = (tmp_path / "wireguard" / "wg0.conf").read_text()
                assert peer_pub in rendered and peer2_pub in rendered and "# PublicEndpoint = 203.0.113.5" in rendered
    db = sqlite3.connect(tmp_path / "tunnbox.db")
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "peer_metadata" not in tables and "refresh_tokens" not in tables
    assert db.execute("SELECT version FROM schema_version").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM peers").fetchone()[0] == 2


async def test_legacy_database_url_is_converted(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    make_env(tmp_path, monkeypatch)
    monkeypatch.delenv("DATABASE_PATH")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/legacy.db")
    from app.config import get_settings

    get_settings.cache_clear()
    assert str(get_settings().db_path) == f"{tmp_path}/legacy.db"
