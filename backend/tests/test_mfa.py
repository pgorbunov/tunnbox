"""TOTP enable, MFA login, recovery codes, disable, admin reset."""

from __future__ import annotations

import time

import pyotp
from httpx import AsyncClient

from tests.conftest import ADMIN, Session, create_user


def totp(secret: str, step_offset: int = 0) -> str:
    """Code for the current step +/- offset (each step may be accepted only once)."""
    return pyotp.TOTP(secret).at(int(time.time()) + 30 * step_offset)


async def enable_mfa(user: Session, password: str = ADMIN["password"]) -> tuple[str, list[str]]:
    assert (await user.post("/api/mfa/setup", json={"password": "wrong-password-x"})).status_code == 403
    r = await user.post("/api/mfa/setup", json={"password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["otpauth_uri"].startswith("otpauth://totp/") and "<svg" in body["qr_svg"]
    secret = body["secret"]
    assert (await user.post("/api/mfa/enable", json={"code": "000000", "password": password})).status_code in (400, 422)
    r = await user.post("/api/mfa/enable", json={"code": totp(secret, -1), "password": password})
    assert r.status_code == 200, r.text
    codes = r.json()["recovery_codes"]
    assert len(codes) == 10 and all(len(c) == 9 and c[4] == "-" for c in codes)
    return secret, codes


async def test_mfa_full_flow(client: AsyncClient, admin: Session) -> None:
    secret, codes = await enable_mfa(admin)
    assert (await admin.get("/api/auth/me")).json()["totp_enabled"] is True

    r = await client.post("/api/auth/login", json=ADMIN)
    assert r.status_code == 200 and r.json() == {"mfa_required": True, "mfa_token": r.json()["mfa_token"]}
    assert "set-cookie" not in r.headers
    mfa_token = r.json()["mfa_token"]

    r = await client.post("/api/auth/login/mfa", json={"mfa_token": mfa_token, "code": "123456"})
    assert r.status_code == 401
    r = await client.post("/api/auth/login/mfa", json={"mfa_token": mfa_token, "code": totp(secret, 0)})
    assert r.status_code == 200 and r.json()["user"]["username"] == "admin"

    # The same MFA token cannot mint a second session (single-use jti), even with a fresh step.
    r = await client.post("/api/auth/login/mfa", json={"mfa_token": mfa_token, "code": totp(secret, 1)})
    assert r.status_code == 401

    # Recovery code works exactly once.
    r = await client.post("/api/auth/login", json=ADMIN)
    mfa_token = r.json()["mfa_token"]
    r = await client.post("/api/auth/login/mfa", json={"mfa_token": mfa_token, "code": codes[0].upper()})
    assert r.status_code == 200
    r = await client.post("/api/auth/login", json=ADMIN)
    r = await client.post("/api/auth/login/mfa", json={"mfa_token": r.json()["mfa_token"], "code": codes[0]})
    assert r.status_code == 401

    # Regenerate and disable.
    r = await admin.post("/api/mfa/recovery-codes", json={"password": ADMIN["password"]})
    assert r.status_code == 200 and len(r.json()["recovery_codes"]) == 10
    r = await admin.post("/api/mfa/disable", json={"password": "wrong-password-x", "code": totp(secret, 1)})
    assert r.status_code == 403
    r = await admin.post("/api/mfa/disable", json={"password": ADMIN["password"], "code": totp(secret, 0)})
    assert r.status_code == 400  # step already consumed by the login above
    r = await admin.post("/api/mfa/disable", json={"password": ADMIN["password"], "code": totp(secret, 1)})
    assert r.status_code == 204
    assert (await admin.get("/api/auth/me")).json()["totp_enabled"] is False
    r = await client.post("/api/auth/login", json=ADMIN)
    assert "access_token" in r.json()

    actions = (await admin.get("/api/audit/actions")).json()
    assert {"auth.mfa_enabled", "auth.mfa_disabled"} <= set(actions)


async def test_mfa_token_cannot_be_used_as_access_token(client: AsyncClient, admin: Session) -> None:
    await enable_mfa(admin)
    r = await client.post("/api/auth/login", json=ADMIN)
    token = r.json()["mfa_token"]
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_admin_can_reset_user_mfa(client: AsyncClient, admin: Session) -> None:
    viewer = await create_user(admin, "viewer", "viewer")
    await enable_mfa(viewer, "another-strong-pass")
    r = await admin.post(f"/api/users/{viewer.user['id']}/mfa/reset")
    assert r.status_code == 204
    assert (await viewer.get("/api/auth/me")).status_code == 401  # sessions revoked on admin reset
    r = await client.post("/api/auth/login", json={"username": "viewer", "password": "another-strong-pass"})
    assert "access_token" in r.json()
