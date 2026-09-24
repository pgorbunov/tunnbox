"""Role enforcement, user management guards and API key scopes."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import Session, create_interface, create_user


async def test_viewer_is_read_only(client: AsyncClient, admin: Session) -> None:
    viewer = await create_user(admin, "viewer", "viewer")
    operator = await create_user(admin, "operator", "operator")
    assert (await viewer.get("/api/interfaces")).status_code == 200
    r = await viewer.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820})
    assert r.status_code == 403
    assert (await viewer.get("/api/audit")).status_code == 403
    assert (await viewer.get("/api/users")).status_code == 403
    assert (await viewer.patch("/api/settings", json={"default_dns": "9.9.9.9"})).status_code == 403
    assert (await viewer.get("/api/settings")).status_code == 200
    # viewer can manage own security
    assert (await viewer.get("/api/auth/sessions")).status_code == 200
    assert (await viewer.post("/api/mfa/setup")).status_code == 200

    r = await operator.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820})
    assert r.status_code == 201
    assert (await operator.get("/api/audit")).status_code == 200
    assert (await operator.get("/api/interfaces/wg0/config")).status_code == 403
    assert (await operator.get("/api/users")).status_code == 403
    assert (await operator.get("/api/system/backup")).status_code == 403
    assert (await admin.get("/api/interfaces/wg0/config")).status_code == 200


async def test_user_management_guards(client: AsyncClient, admin: Session) -> None:
    me = admin.user["id"]
    assert (await admin.patch(f"/api/users/{me}", json={"role": "viewer"})).status_code == 400
    assert (await admin.patch(f"/api/users/{me}", json={"is_active": False})).status_code == 400
    assert (await admin.delete(f"/api/users/{me}")).status_code == 400
    r = await admin.post("/api/users", json={"username": "admin", "password": "another-strong-pass", "role": "admin"})
    assert r.status_code == 409
    second = await create_user(admin, "second", "admin")
    # Disabling the other admin is fine while we remain; disabling revokes their sessions.
    r = await admin.patch(f"/api/users/{second.user['id']}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await second.get("/api/auth/me")).status_code == 401
    users = (await admin.get("/api/users")).json()
    assert {u["username"] for u in users} == {"admin", "second"}
    assert (await admin.delete(f"/api/users/{second.user['id']}")).status_code == 204


async def test_api_key_lifecycle_and_scopes(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin)
    r = await admin.post("/api/api-keys", json={"name": "ci", "scopes": ["read"]})
    assert r.status_code == 201, r.text
    body = r.json()
    key = body["key"]
    assert key.startswith("tb_") and body["prefix"] == key[:8] and body["scopes"] == ["read"]
    listed = (await admin.get("/api/api-keys")).json()
    assert len(listed) == 1 and "key" not in listed[0]

    bearer = {"Authorization": f"Bearer {key}"}
    header = {"X-API-Key": key}
    assert (await client.get("/api/interfaces", headers=bearer)).status_code == 200
    assert (await client.get("/api/interfaces", headers=header)).status_code == 200
    # read-only key cannot write
    r = await client.post("/api/interfaces/wg0/peers", json={"name": "p"}, headers=bearer)
    assert r.status_code == 403
    # keys cannot touch auth/mfa/api-keys
    assert (await client.get("/api/auth/me", headers=bearer)).status_code == 403
    assert (await client.post("/api/mfa/setup", headers=bearer)).status_code == 403
    assert (await client.get("/api/api-keys", headers=bearer)).status_code == 403
    assert (await client.get("/api/users", headers=bearer)).status_code == 403

    r = await admin.post("/api/api-keys", json={"name": "peers", "scopes": ["peers:write"]})
    peers_key = {"Authorization": f"Bearer {r.json()['key']}"}
    r = await client.post("/api/interfaces/wg0/peers", json={"name": "from-key"}, headers=peers_key)
    assert r.status_code == 201
    r = await client.post("/api/interfaces", json={"name": "wg1", "address": "10.9.0.1/24", "listen_port": 51821}, headers=peers_key)
    assert r.status_code == 403
    audit = (await admin.get("/api/audit", params={"action": "peer.created"})).json()
    assert audit["items"][0]["username"] == "api-key:peers"

    r = await admin.post("/api/api-keys", json={"name": "root", "scopes": ["admin"]})
    admin_key = {"Authorization": f"Bearer {r.json()['key']}"}
    assert (await client.get("/api/users", headers=admin_key)).status_code == 200

    assert (await admin.delete(f"/api/api-keys/{body['id']}")).status_code == 204
    assert (await client.get("/api/interfaces", headers=bearer)).status_code == 401
    listed = (await admin.get("/api/api-keys")).json()
    assert next(k for k in listed if k["id"] == body["id"])["revoked_at"] is not None


async def test_api_key_cannot_exceed_owner_role(client: AsyncClient, admin: Session) -> None:
    operator = await create_user(admin, "operator", "operator")
    r = await operator.post("/api/api-keys", json={"name": "x", "scopes": ["admin"]})
    assert r.status_code == 400
    r = await operator.post("/api/api-keys", json={"name": "x", "scopes": ["interfaces:write"]})
    assert r.status_code == 201
    key = r.json()["key"]
    # Demote the owner: existing key loses write ability.
    await admin.patch(f"/api/users/{operator.user['id']}", json={"role": "viewer"})
    r = await client.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820}, headers={"X-API-Key": key})
    assert r.status_code in (401, 403)
    assert (await admin.get("/api/api-keys", params={"all": "true"})).status_code == 200
