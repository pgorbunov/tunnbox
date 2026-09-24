"""Setup, login, refresh rotation, reuse detection, logout, lockout, sessions, password change."""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import iso, utcnow
from tests.conftest import ADMIN, Session, do_login, do_setup


async def test_status_and_setup_flow(client: AsyncClient) -> None:
    r = await client.get("/api/auth/status")
    assert r.json() == {"setup_required": True, "version": "2.0.0"}
    r = await client.post("/api/auth/setup", json={"username": "admin", "password": "short"})
    assert r.status_code == 400
    admin = await do_setup(client)
    assert admin.user["role"] == "admin" and admin.user["totp_enabled"] is False
    assert (await client.get("/api/auth/status")).json()["setup_required"] is False
    r = await client.post("/api/auth/setup", json=ADMIN)
    assert r.status_code == 409
    me = await admin.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "admin"
    cookie = client.cookies.get("tb_refresh")
    assert cookie


async def test_refresh_rotation_and_reuse_detection(client: AsyncClient, admin: Session) -> None:
    first = client.cookies.get("tb_refresh")
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200 and "access_token" in r.json() and r.json()["user"]["username"] == "admin"
    second = client.cookies.get("tb_refresh")
    assert second and second != first
    # Reusing the rotated token must fail and revoke the whole session.
    client.cookies.set("tb_refresh", first, path="/api/auth")
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 401
    client.cookies.set("tb_refresh", second, path="/api/auth")
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 401
    assert (await admin.get("/api/auth/me")).status_code == 401
    audit = await (await do_login(client, **ADMIN)).get("/api/audit", params={"action": "auth.session_revoked"})
    assert audit.json()["total"] >= 1


async def test_refresh_requires_matching_origin(client: AsyncClient, admin: Session) -> None:
    r = await client.post("/api/auth/refresh", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = await client.post("/api/auth/refresh", headers={"Origin": "http://testserver"})
    assert r.status_code == 200


async def test_login_sets_cookie_flags(client: AsyncClient, admin: Session) -> None:
    r = await client.post("/api/auth/login", json=ADMIN)
    set_cookie = r.headers["set-cookie"]
    assert "HttpOnly" in set_cookie and "SameSite=strict" in set_cookie and "Path=/api/auth" in set_cookie


async def test_logout_revokes_session(client: AsyncClient, admin: Session) -> None:
    r = await admin.post("/api/auth/logout")
    assert r.status_code == 204
    assert (await admin.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_generic_errors_and_lockout(client: AsyncClient, admin: Session) -> None:
    r = await client.post("/api/auth/login", json={"username": "nobody", "password": "whatever-pass"})
    assert r.status_code == 401 and r.json()["detail"] == "Invalid username or password"
    for _ in range(3):
        r = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
    assert r.status_code == 401
    r = await client.post("/api/auth/login", json=ADMIN)
    assert r.status_code == 423 and r.json()["detail"] == "Account temporarily locked"
    audit = await admin.get("/api/audit", params={"action": "auth.locked"})
    assert audit.json()["total"] == 1


async def test_lockout_expires_and_success_resets(client: AsyncClient, admin: Session, app) -> None:  # noqa: ANN001
    from app.db.connection import connect

    for _ in range(2):
        await client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
    assert (await client.post("/api/auth/login", json=ADMIN)).status_code == 200
    async with connect(app.state.ctx.db_path) as db:
        row = await db.execute_fetchall("SELECT failed_logins FROM users WHERE username='admin'")
        assert row[0][0] == 0
        await db.execute("UPDATE users SET locked_until = ? WHERE username='admin'", (iso(utcnow() - timedelta(minutes=1)),))
    assert (await client.post("/api/auth/login", json=ADMIN)).status_code == 200


async def test_sessions_list_and_revoke(client: AsyncClient, admin: Session) -> None:
    other = await do_login(client, **ADMIN)
    r = await admin.get("/api/auth/sessions")
    sessions = r.json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["current"]]
    assert len(current) == 1
    other_id = next(s["id"] for s in sessions if not s["current"])
    assert (await admin.delete(f"/api/auth/sessions/{other_id}")).status_code == 204
    assert (await other.get("/api/auth/me")).status_code == 401
    third = await do_login(client, **ADMIN)
    assert (await admin.delete("/api/auth/sessions")).status_code == 204
    assert (await third.get("/api/auth/me")).status_code == 401
    assert (await admin.get("/api/auth/me")).status_code == 200


async def test_password_change_revokes_other_sessions(client: AsyncClient, admin: Session) -> None:
    other = await do_login(client, **ADMIN)
    r = await admin.patch("/api/auth/me/password", json={"current_password": "wrong-pass-here", "new_password": "brand-new-password"})
    assert r.status_code == 403
    r = await admin.patch("/api/auth/me/password", json={"current_password": ADMIN["password"], "new_password": "admin"})
    assert r.status_code == 400
    r = await admin.patch("/api/auth/me/password", json={"current_password": ADMIN["password"], "new_password": "brand-new-password"})
    assert r.status_code == 204
    assert (await other.get("/api/auth/me")).status_code == 401
    assert (await admin.get("/api/auth/me")).status_code == 200
    assert (await client.post("/api/auth/login", json=ADMIN)).status_code == 401
    assert (await client.post("/api/auth/login", json={"username": "admin", "password": "brand-new-password"})).status_code == 200


async def test_rate_limit_login(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    from tests.conftest import make_env

    make_env(tmp_path, monkeypatch, LOGIN_RATE_LIMIT="2/minute")
    from httpx import ASGITransport

    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            await c.post("/api/auth/login", json={"username": "x", "password": "y-password"})
            await c.post("/api/auth/login", json={"username": "x", "password": "y-password"})
            r = await c.post("/api/auth/login", json={"username": "x", "password": "y-password"})
            assert r.status_code == 429 and "retry-after" in r.headers


@pytest.mark.parametrize("path", ["/api/interfaces", "/api/auth/me", "/api/settings"])
async def test_unauthenticated_rejected(client: AsyncClient, admin: Session, path: str) -> None:
    assert (await client.get(path)).status_code == 401
    assert (await client.get(path, headers={"Authorization": "Bearer nonsense"})).status_code == 401
