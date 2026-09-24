"""Regression tests for the adversarial security review (H1-H3, M1-M12, selected LOW items)."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path
from typing import Any

import bcrypt
import pyotp
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import BackendError
from app.core.security import hash_password_async, verify_password_async
from app.main import create_app
from app.services import peers as peers_service
from app.services.wireguard import keys
from tests.conftest import ADMIN, Session, create_interface, create_peer, create_user, do_login, do_setup, make_env


async def _fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str):  # noqa: ANN202
    make_env(tmp_path, monkeypatch, **env)
    app = create_app()
    return app


# ---------------------------------------------------------------- HIGH


async def test_h1_legacy_non_admin_becomes_viewer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = sqlite3.connect(tmp_path / "tunnbox.db")
    db.executescript(
        """CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, hashed_password TEXT, is_admin BOOLEAN DEFAULT FALSE, created_at TIMESTAMP);
           CREATE TABLE refresh_tokens (id INTEGER PRIMARY KEY, user_id INT, token TEXT, expires_at TEXT);
           CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, details TEXT, ip_address TEXT, created_at TIMESTAMP);"""
    )
    pw = bcrypt.hashpw(b"legacy-password-1", bcrypt.gensalt(4)).decode()
    db.execute("INSERT INTO users (username, hashed_password, is_admin) VALUES ('boss', ?, 1)", (pw,))
    db.execute("INSERT INTO users (username, hashed_password, is_admin) VALUES ('intern', ?, 0)", (pw,))
    db.execute("INSERT INTO users (username, hashed_password, is_admin) VALUES ('Intern', ?, 0)", (pw,))  # case collision
    stamp = "2099-01-01 00:00:00"  # far future so the retention job cannot prune it during the test
    db.execute("INSERT INTO audit_logs (user_id, action, details, ip_address, created_at) VALUES (1, 'login', 'ok', '1.2.3.4', ?)", (stamp,))
    db.execute("INSERT INTO audit_logs (user_id, action, details, ip_address, created_at) VALUES (1, 'frobnicate', '{\"a\":1}', NULL, ?)", (stamp,))
    db.commit()
    db.close()
    app = await _fresh(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            boss = await do_login(c, "boss", "legacy-password-1")
            users = {u["username"]: u["role"] for u in (await boss.get("/api/users")).json()}
            assert users == {"boss": "admin", "intern": "viewer", "Intern_2": "viewer"}
            intern = await do_login(c, "intern", "legacy-password-1")
            assert (await intern.get("/api/users")).status_code == 403
            audit = (await boss.get("/api/audit", params={"page_size": 100})).json()["items"]
            legacy = [e for e in audit if e["created_at"].startswith("2099")]
            assert {e["action"] for e in legacy} == {"auth.login", "legacy.frobnicate"}
            assert all(e["username"] == "boss" for e in legacy)
            assert next(e for e in legacy if e["action"] == "auth.login")["details"] == {"legacy": "ok"}


async def test_h2_import_skips_unsupported_and_rolls_back_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wg = tmp_path / "wireguard"
    wg.mkdir()
    priv, _ = keys.generate_keypair()
    k1, k2 = keys.generate_keypair()[1], keys.generate_keypair()[1]
    unsupported = f"[Interface]\nPrivateKey = {priv}\nAddress = 10.9.0.1/24\nListenPort = 51900\nTable = off\n\n[Peer]\nPublicKey = {k1}\nAllowedIPs = 10.9.0.2/32\nEndpoint = 1.2.3.4:51820\n"
    (wg / "wg0.conf").write_text(unsupported)
    duplicate = f"[Interface]\nPrivateKey = {priv}\nAddress = 10.10.0.1/24\nListenPort = 51901\n\n[Peer]\nPublicKey = {k1}\nAllowedIPs = 10.10.0.2/32\n\n[Peer]\nPublicKey = {k1}\nAllowedIPs = 10.10.0.3/32\n\n[Peer]\nPublicKey = {k2}\nAllowedIPs = 10.10.0.4/32\n"
    (wg / "wg1.conf").write_text(duplicate)
    clean = f"[Interface]\nPrivateKey = {priv}\nAddress = 10.11.0.1/24\nListenPort = 51902\n\n[Peer]\nPublicKey = {k2}\nAllowedIPs = 10.11.0.2/32\n"
    (wg / "wg2.conf").write_text(clean)
    db = sqlite3.connect(tmp_path / "tunnbox.db")
    db.executescript("CREATE TABLE peer_metadata (id INTEGER PRIMARY KEY, interface_name TEXT, public_key TEXT, name TEXT, private_key TEXT);")
    db.commit()
    db.close()
    app = await _fresh(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        pass
    db = sqlite3.connect(tmp_path / "tunnbox.db")
    assert [r[0] for r in db.execute("SELECT name FROM interfaces")] == ["wg2"]
    assert db.execute("SELECT COUNT(*) FROM peers").fetchone()[0] == 1  # the partial wg1 import was rolled back
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "peer_metadata" in tables  # kept because not every file imported cleanly
    assert (wg / "wg0.conf").read_text() == unsupported  # untouched
    assert (wg / "wg1.conf").read_text() == duplicate
    assert (wg / "wg2.conf.v1.bak").read_text() == clean
    assert (wg / "wg2.conf").read_text() != clean  # re-rendered
    assert not (wg / "wg0.conf.v1.bak").exists()


async def test_h3_concurrent_failed_logins_lock_account(client: AsyncClient, admin: Session, app: FastAPI) -> None:
    await create_user(admin, "view", "viewer", "viewer-password-1")
    rs = await asyncio.gather(*[client.post("/api/auth/login", json={"username": "view", "password": "wrong-password-x"}) for _ in range(10)])
    assert {r.status_code for r in rs} <= {401, 423}
    r = await client.post("/api/auth/login", json={"username": "view", "password": "viewer-password-1"})
    assert r.status_code == 423
    audit = (await admin.get("/api/audit", params={"action": "auth.locked"})).json()
    assert audit["total"] >= 1


# ---------------------------------------------------------------- MEDIUM


async def test_m1_mfa_lockout_replay_and_recovery_single_spend(client: AsyncClient, admin: Session) -> None:
    r = await admin.post("/api/mfa/setup", json={"password": ADMIN["password"]})
    secret = r.json()["secret"]
    r = await admin.post("/api/mfa/enable", json={"code": pyotp.TOTP(secret).at(int(time.time()) - 30), "password": ADMIN["password"]})
    codes = r.json()["recovery_codes"]
    client.cookies.clear()
    mt = (await client.post("/api/auth/login", json=ADMIN)).json()["mfa_token"]
    statuses = [(await client.post("/api/auth/login/mfa", json={"mfa_token": mt, "code": "000000"})).status_code for _ in range(4)]
    assert statuses[:3] == [401, 401, 401] and statuses[3] == 423  # bad codes count toward lockout
    assert (await client.post("/api/auth/login", json=ADMIN)).status_code == 423
    r = await client.post("/api/auth/login/mfa", json={"mfa_token": mt, "code": pyotp.TOTP(secret).now()})
    assert r.status_code == 423  # locked even with a valid code
    from app.db.connection import connect

    async def unlock() -> None:
        async with connect(client._transport.app.state.ctx.db_path, immediate=True) as db:  # type: ignore[attr-defined]
            await db.execute("UPDATE users SET locked_until = NULL, failed_logins = 0")

    await unlock()
    code = pyotp.TOTP(secret).now()
    rs = await asyncio.gather(*[client.post("/api/auth/login/mfa", json={"mfa_token": mt, "code": code}) for _ in range(3)])
    assert sorted(r.status_code for r in rs) == [200, 401, 401]  # token + step usable exactly once
    r = await client.post("/api/auth/login", json=ADMIN)
    assert r.status_code == 200 and "mfa_token" in r.json(), r.text
    mt2 = r.json()["mfa_token"]
    assert (await client.post("/api/auth/login/mfa", json={"mfa_token": mt2, "code": code})).status_code == 401  # step already consumed
    await unlock()  # the replay above was the third failure and locked the account again
    mt3 = (await client.post("/api/auth/login", json=ADMIN)).json()["mfa_token"]
    mt4 = (await client.post("/api/auth/login", json=ADMIN)).json()["mfa_token"]
    rs = await asyncio.gather(
        client.post("/api/auth/login/mfa", json={"mfa_token": mt3, "code": codes[0]}),
        client.post("/api/auth/login/mfa", json={"mfa_token": mt4, "code": codes[0]}),
    )
    assert sorted(r.status_code for r in rs) == [200, 401]  # recovery code spent once


async def test_m2_forwarded_for_is_walked_from_the_right(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = await _fresh(tmp_path, monkeypatch, TRUSTED_PROXIES="127.0.0.1, 10.0.0.0/8")
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            admin = await do_setup(c)
            xff = {"X-Forwarded-For": "6.6.6.6, 203.0.113.9, 10.1.2.3"}
            await c.post("/api/auth/login", json={"username": "admin", "password": "wrong-password-x"}, headers=xff)
            entry = (await admin.get("/api/audit", params={"action": "auth.login_failed"})).json()["items"][0]
            assert entry["ip"] == "203.0.113.9"  # first untrusted hop from the right, not the spoofable left-most
            await c.post("/api/auth/login", json={"username": "admin", "password": "wrong-password-x"}, headers={"X-Forwarded-For": "10.9.9.9"})
            entry = (await admin.get("/api/audit", params={"action": "auth.login_failed"})).json()["items"][0]
            assert entry["ip"] == "10.9.9.9"  # all hops trusted: fall back to the left-most


async def test_m3_config_qr_share_require_write_privileges(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin)
    peer = await create_peer(admin)
    viewer = await create_user(admin, "viewer", "viewer")
    assert (await viewer.get(f"/api/peers/{peer['id']}")).status_code == 200
    assert (await viewer.get(f"/api/peers/{peer['id']}/config")).status_code == 403
    assert (await viewer.get(f"/api/peers/{peer['id']}/qr")).status_code == 403
    assert (await viewer.post(f"/api/peers/{peer['id']}/share", json={})).status_code == 403
    r = await admin.post("/api/api-keys", json={"name": "ro", "scopes": ["read"]})
    ro = {"X-API-Key": r.json()["key"]}
    assert (await client.get(f"/api/peers/{peer['id']}/config", headers=ro)).status_code == 403
    r = await admin.post("/api/api-keys", json={"name": "rw", "scopes": ["peers:write"]})
    rw = {"X-API-Key": r.json()["key"]}
    assert (await client.get(f"/api/peers/{peer['id']}/qr", headers=rw)).status_code == 200
    entry = (await admin.get("/api/audit", params={"action": "peer.config_downloaded"})).json()["items"][0]
    assert entry["details"]["format"] == "qr" and entry["username"] == "api-key:rw"


async def test_m4_concurrent_refresh_only_one_wins(client: AsyncClient, admin: Session, app: FastAPI) -> None:
    token = client.cookies.get("tb_refresh")

    async def refresh() -> int:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver", cookies={"tb_refresh": token}) as cc:
            return (await cc.post("/api/auth/refresh")).status_code

    statuses = sorted(await asyncio.gather(*[refresh() for _ in range(4)]))
    assert statuses == [200, 401, 401, 401]
    assert (await admin.get("/api/auth/me")).status_code == 401  # losers were treated as reuse -> session revoked


async def test_m5_share_link_concurrency_and_invalidation(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin)
    peer = await create_peer(admin)
    token = (await admin.post(f"/api/peers/{peer['id']}/share", json={"max_uses": 2})).json()["token"]
    rs = await asyncio.gather(*[client.get(f"/api/share/{token}") for _ in range(6)])
    assert sorted(r.status_code for r in rs) == [200, 200, 410, 410, 410, 410]
    token = (await admin.post(f"/api/peers/{peer['id']}/share", json={"max_uses": 5})).json()["token"]
    await admin.post(f"/api/peers/{peer['id']}/rotate-keys")
    assert (await client.get(f"/api/share/{token}")).status_code == 404  # link deleted on rotation
    token = (await admin.post(f"/api/peers/{peer['id']}/share", json={"max_uses": 5})).json()["token"]
    await admin.post(f"/api/peers/{peer['id']}/disable")
    assert (await client.get(f"/api/share/{token}")).status_code == 404  # and on disable


async def test_m6_concurrent_peer_creation_gets_distinct_addresses(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin)
    rs = await asyncio.gather(*[admin.post("/api/interfaces/wg0/peers", json={"name": f"p{i}"}) for i in range(6)])
    assert all(r.status_code == 201 for r in rs)
    ips = [r.json()["allowed_ips"] for r in rs]
    assert len(set(ips)) == 6
    rs = await asyncio.gather(*[admin.post("/api/interfaces/wg0/peers", json={"name": f"m{i}", "allowed_ips": "10.8.0.100/32"}) for i in range(3)])
    assert sorted(r.status_code for r in rs) == [201, 409, 409]


async def test_m7_setup_race_creates_one_admin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = await _fresh(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            rs = await asyncio.gather(*[c.post("/api/auth/setup", json={"username": f"adm{i}", "password": "correct-horse-battery"}) for i in range(5)])
            assert sorted(r.status_code for r in rs) == [200, 409, 409, 409, 409]
            token = next(r.json()["access_token"] for r in rs if r.status_code == 200)
            users = (await c.get("/api/users", headers={"Authorization": f"Bearer {token}"})).json()
            assert len(users) == 1


async def test_m8_peer_route_policy(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin, address="10.8.0.1/24, fd00:8::1/64")
    operator = await create_user(admin, "op", "operator")
    for payload, status in (
        ({"name": "a", "allowed_ips": "0.0.0.0/0"}, 409),
        ({"name": "b", "allowed_ips": "::/0"}, 409),
        ({"name": "c", "allowed_ips": "fe80::1%eth0/128"}, 422),
        ({"name": "d", "allowed_ips": "10.8.0.0/25"}, 409),  # overlaps interface subnet
        ({"name": "e", "allowed_ips": "192.168.5.7/32"}, 409),  # host route outside interface
        ({"name": "f", "allowed_ips": "192.168.5.0/24"}, 409),  # no host route at all
        ({"name": "g", "client_dns": "fe80::1%lo"}, 422),
    ):
        r = await admin.post("/api/interfaces/wg0/peers", json=payload)
        assert r.status_code == status, (payload, r.text)
    r = await operator.post("/api/interfaces/wg0/peers", json={"name": "op1", "allowed_ips": "10.8.0.9/32, 192.168.5.0/24"})
    assert r.status_code == 403  # wider routes are admin-only
    r = await admin.post("/api/interfaces/wg0/peers", json={"name": "site", "allowed_ips": "10.8.0.9/32, 192.168.5.0/24"})
    assert r.status_code == 201
    r = await admin.post("/api/interfaces/wg0/peers", json={"name": "clash", "allowed_ips": "10.8.0.10/32, 192.168.5.128/25"})
    assert r.status_code == 409  # overlaps a route already given to another peer
    r = await admin.post("/api/interfaces/wg0/peers", json={"name": "ok", "allowed_ips": "10.8.0.10/32, fd00:8::10/128"})
    assert r.status_code == 201


async def test_m9_expiry_job_commits_per_peer_despite_backend_failure(client: AsyncClient, admin: Session, app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import timedelta

    from app.core.security import iso, utcnow

    await create_interface(admin)
    await create_interface(admin, name="wg1", address="10.9.0.1/24", port=51821)
    past = iso(utcnow() - timedelta(minutes=1))
    p0 = await create_peer(admin, iface="wg0", name="a", expires_at=past)
    p1 = await create_peer(admin, iface="wg1", name="b", expires_at=past)

    async def failing_sync(name: str) -> None:
        if name == "wg0":
            raise BackendError("syncconf exploded")

    monkeypatch.setattr(app.state.ctx.backend, "sync", failing_sync)
    assert await peers_service.expire_peers(app.state.ctx) == 2
    for peer in (p0, p1):
        assert (await admin.get(f"/api/peers/{peer['id']}")).json()["enabled"] is False
    conf = (app.state.ctx.settings.config_dir / "wg0.conf").read_text()
    assert p0["public_key"] not in conf  # file re-rendered from DB even though sync failed
    assert await peers_service.expire_peers(app.state.ctx) == 0  # no endless retry


async def test_m10_backend_failure_after_commit_returns_502_without_orphan(client: AsyncClient, admin: Session, app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_up(name: str) -> None:
        raise BackendError("wg-quick up failed")

    monkeypatch.setattr(app.state.ctx.backend, "up", failing_up)
    r = await admin.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820})
    assert r.status_code == 502 and r.json()["code"] == "backend_error"
    listed = (await admin.get("/api/interfaces")).json()
    assert [i["name"] for i in listed] == ["wg0"] and listed[0]["is_active"] is False
    assert (app.state.ctx.settings.config_dir / "wg0.conf").is_file()  # DB and file agree
    # the (mock) peer flow still works and a second create is a clean 409, never a duplicate import
    assert (await admin.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820})).status_code == 409
    from app.services import importer

    assert await importer.import_legacy_configs(app.state.ctx) == 0


async def test_m11_scripts_admin_only_and_omitted_when_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = await _fresh(tmp_path, monkeypatch, WG_ALLOW_CUSTOM_SCRIPTS="true")
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            admin = await do_setup(c)
            operator = await create_user(admin, "op", "operator")
            r = await operator.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820, "post_up": "echo x"})
            assert r.status_code == 403
            r = await admin.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820, "post_up": "echo up"})
            assert r.status_code == 201
            assert (await operator.patch("/api/interfaces/wg0", json={"post_down": "echo d"})).status_code == 403
            assert (await operator.patch("/api/interfaces/wg0", json={"dns": "9.9.9.9"})).status_code == 200
            assert "PostUp = echo up" in (tmp_path / "wireguard" / "wg0.conf").read_text()
    # Same database, scripts now disabled by env: renderer must drop them.
    app = await _fresh(tmp_path, monkeypatch, WG_ALLOW_CUSTOM_SCRIPTS="false")
    async with app.router.lifespan_context(app):
        text = (tmp_path / "wireguard" / "wg0.conf").read_text()
        assert "PostUp" not in text and "PrivateKey" in text
        assert "wg0" in app.state.ctx.scripts_warned


async def test_m12_bcrypt_runs_off_the_event_loop() -> None:
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.005)

    task = asyncio.create_task(ticker())
    hashed = await hash_password_async("correct-horse-battery", 10)
    assert await verify_password_async("correct-horse-battery", hashed, hashed)
    task.cancel()
    assert ticks > 1  # the loop kept running while bcrypt worked in a thread


# ---------------------------------------------------------------- LOW


async def test_l1_passwords_over_72_bytes_rejected(client: AsyncClient) -> None:
    r = await client.post("/api/auth/setup", json={"username": "z", "password": "é" * 40})
    assert r.status_code == 400 and "72 bytes" in r.json()["detail"]
    admin = await do_setup(client)
    r = await admin.patch("/api/auth/me/password", json={"current_password": ADMIN["password"], "new_password": "a" * 100})
    assert r.status_code == 400
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "x" * 120})
    assert r.status_code == 401


async def test_l2_500_responses_carry_security_headers(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(_ctx: Any) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("app.services.auth.status", boom)
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver") as c:
        r = await c.get("/api/auth/status")
        assert r.status_code == 500 and r.json()["detail"] == "Internal server error"
        assert "content-security-policy" in r.headers and r.headers["x-frame-options"] == "DENY"


async def test_l7_secret_key_persisted_next_to_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    make_env(tmp_path, monkeypatch, SECRET_KEY="")
    first = get_settings().secret_key
    key_file = tmp_path / ".secret_key"
    assert key_file.is_file() and oct(key_file.stat().st_mode & 0o777) == "0o600" and key_file.read_text().strip() == first
    get_settings.cache_clear()
    assert get_settings().secret_key == first  # reused on the next start
    monkeypatch.setenv("SECRET_KEY", "explicit-env-key")
    get_settings.cache_clear()
    assert get_settings().secret_key == "explicit-env-key"  # env wins


def test_l9_cors_default_is_empty_unless_debug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    make_env(tmp_path, monkeypatch)
    assert get_settings().cors_origins == []
    monkeypatch.setenv("DEBUG", "true")
    get_settings.cache_clear()
    assert "http://localhost:5173" in get_settings().cors_origins
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example")
    get_settings.cache_clear()
    assert get_settings().cors_origins == ["https://a.example"]


