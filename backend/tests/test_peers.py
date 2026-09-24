"""Peer CRUD, IP assignment, client config, disable/expiry, rotation, bulk and share links."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from httpx import AsyncClient

from app.core.security import iso, utcnow
from app.services import peers as peers_service
from tests.conftest import Session, conf_text, create_interface, create_peer


async def test_peer_create_auto_ip_v4(client: AsyncClient, admin: Session, env: Path) -> None:
    await create_interface(admin)
    assert (await admin.get("/api/interfaces/wg0/next-ip")).json() == {"allowed_ips": "10.8.0.2/32"}
    p1 = await create_peer(admin, name="laptop")
    p2 = await create_peer(admin, name="phone", allowed_ips="auto")
    assert p1["allowed_ips"] == "10.8.0.2/32" and p2["allowed_ips"] == "10.8.0.3/32"
    assert p1["has_private_key"] and p1["has_preshared_key"] and p1["status"] == "offline"
    assert p1["client_allowed_ips"] == "0.0.0.0/0, ::/0" and p1["persistent_keepalive"] == 25
    p3 = await create_peer(admin, name="manual", allowed_ips="10.8.0.50")
    assert p3["allowed_ips"] == "10.8.0.50/32"
    r = await admin.post("/api/interfaces/wg0/peers", json={"name": "dup", "allowed_ips": "10.8.0.2/32"})
    assert r.status_code == 409
    conf = conf_text(env)
    assert conf.count("[Peer]") == 3 and "# Name: laptop" in conf and "PresharedKey = " in conf
    iface = (await admin.get("/api/interfaces/wg0")).json()
    assert iface["peer_count"] == 3


async def test_peer_auto_ip_dual_stack(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin, address="10.8.0.1/24, fd00:8::1/64")
    peer = await create_peer(admin)
    assert peer["allowed_ips"] == "10.8.0.2/32, fd00:8::2/128"
    peer = await create_peer(admin, name="second")
    assert peer["allowed_ips"] == "10.8.0.3/32, fd00:8::3/128"


async def test_client_config_and_split_tunnel_override(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin, dns="10.8.0.1")
    peer = await create_peer(admin, client_dns="9.9.9.9")
    r = await admin.get(f"/api/peers/{peer['id']}/config")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert 'filename="laptop.conf"' in r.headers["content-disposition"]
    text = r.text
    assert "[Interface]" in text and "Address = 10.8.0.2/32" in text and "DNS = 9.9.9.9" in text
    assert "AllowedIPs = 0.0.0.0/0, ::/0" in text and "Endpoint = vpn.example.com:51820" in text
    assert "PresharedKey = " in text and "PersistentKeepalive = 25" in text
    r = await admin.get(f"/api/peers/{peer['id']}/config", params={"allowed_ips": "10.8.0.0/24, 192.168.1.0/24"})
    assert "AllowedIPs = 10.8.0.0/24, 192.168.1.0/24" in r.text
    r = await admin.get(f"/api/peers/{peer['id']}/config", params={"allowed_ips": "garbage"})
    assert r.status_code == 422
    r = await admin.get(f"/api/peers/{peer['id']}/qr")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    audit = (await admin.get("/api/audit", params={"action": "peer.config_downloaded"})).json()
    assert audit["total"] == 3 and {e["details"]["format"] for e in audit["items"]} == {"conf", "qr"}


async def test_peer_update_disable_and_conf_rendering(client: AsyncClient, admin: Session, env: Path) -> None:
    await create_interface(admin)
    peer = await create_peer(admin)
    key = peer["public_key"]
    assert key in conf_text(env)
    r = await admin.post(f"/api/peers/{peer['id']}/disable")
    assert r.json()["enabled"] is False and r.json()["status"] == "disabled"
    assert key not in conf_text(env)
    r = await admin.post(f"/api/peers/{peer['id']}/enable")
    assert r.json()["enabled"] is True and key in conf_text(env)
    r = await admin.patch(f"/api/peers/{peer['id']}", json={"name": "renamed", "persistent_keepalive": 0, "notes": "hi"})
    body = r.json()
    assert body["name"] == "renamed" and body["persistent_keepalive"] == 0 and body["notes"] == "hi"
    assert "PersistentKeepalive" not in conf_text(env) and "# Name: renamed" in conf_text(env)
    assert (await admin.get(f"/api/peers/{peer['id']}")).json()["name"] == "renamed"
    assert (await admin.delete(f"/api/peers/{peer['id']}")).status_code == 204
    assert (await admin.get(f"/api/peers/{peer['id']}")).status_code == 404
    assert key not in conf_text(env)


async def test_peer_expiry_job(client: AsyncClient, admin: Session, env: Path, app) -> None:  # noqa: ANN001
    await create_interface(admin)
    past = iso(utcnow() - timedelta(minutes=1))
    future = iso(utcnow() + timedelta(days=1))
    expired = await create_peer(admin, name="old", expires_at=past)
    fresh = await create_peer(admin, name="new", expires_at=future)
    assert expired["status"] == "expired" and fresh["status"] == "offline"
    assert expired["public_key"] in conf_text(env)
    assert await peers_service.expire_peers(app.state.ctx) == 1
    assert expired["public_key"] not in conf_text(env) and fresh["public_key"] in conf_text(env)
    body = (await admin.get(f"/api/peers/{expired['id']}")).json()
    assert body["enabled"] is False and body["status"] == "expired"
    audit = (await admin.get("/api/audit", params={"action": "peer.auto_disabled"})).json()
    assert audit["total"] == 1 and audit["items"][0]["username"] == "system"
    r = await admin.post("/api/interfaces/wg0/peers", json={"name": "bad", "expires_at": "not-a-date"})
    assert r.status_code == 422


async def test_rotate_keys(client: AsyncClient, admin: Session, env: Path) -> None:
    await create_interface(admin)
    peer = await create_peer(admin)
    old_config = (await admin.get(f"/api/peers/{peer['id']}/config")).text
    r = await admin.post(f"/api/peers/{peer['id']}/rotate-keys")
    assert r.status_code == 200 and r.json()["public_key"] != peer["public_key"]
    assert r.json()["public_key"] in conf_text(env) and peer["public_key"] not in conf_text(env)
    assert (await admin.get(f"/api/peers/{peer['id']}/config")).text != old_config


async def test_bulk_and_search(client: AsyncClient, admin: Session, env: Path) -> None:
    await create_interface(admin)
    await create_interface(admin, name="wg1", address="10.9.0.1/24", port=51821)
    ids = [(await create_peer(admin, name=f"peer-{i}"))["id"] for i in range(3)]
    other = await create_peer(admin, iface="wg1", name="remote")
    r = await admin.post("/api/peers/bulk", json={"ids": ids[:2], "action": "disable"})
    assert r.json() == {"affected": 2}
    page = (await admin.get("/api/peers", params={"status": "disabled"})).json()
    assert page["total"] == 2 and page["page"] == 1
    page = (await admin.get("/api/peers", params={"q": "remote"})).json()
    assert page["total"] == 1 and page["items"][0]["interface_name"] == "wg1"
    page = (await admin.get("/api/peers", params={"interface": "wg0", "page_size": 2})).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    listed = (await admin.get("/api/interfaces/wg0/peers", params={"sort": "created", "order": "desc"})).json()
    assert [p["name"] for p in listed] == ["peer-2", "peer-1", "peer-0"]
    r = await admin.post("/api/peers/bulk", json={"ids": ids + [other["id"]], "action": "delete"})
    assert r.json() == {"affected": 4}
    assert (await admin.get("/api/peers")).json()["total"] == 0
    assert "[Peer]" not in conf_text(env, "wg1")


async def test_share_link_happy_path_and_exhaustion(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin)
    peer = await create_peer(admin)
    r = await admin.post(f"/api/peers/{peer['id']}/share", json={"max_uses": 2, "expires_in_hours": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url_path"] == f"/share/{body['token']}" and body["max_uses"] == 2
    token = body["token"]
    r = await client.get(f"/api/share/{token}")  # public, no auth
    assert r.status_code == 200
    payload = r.json()
    assert payload["peer_name"] == "laptop" and payload["interface_name"] == "wg0" and payload["remaining_uses"] == 1
    assert "[Interface]" in payload["config"] and payload["qr_png_base64"]
    r = await client.get(f"/api/share/{token}")
    assert r.status_code == 200 and r.json()["remaining_uses"] == 0
    r = await client.get(f"/api/share/{token}")
    assert r.status_code == 410
    assert (await client.get("/api/share/does-not-exist")).status_code == 404
    audit = (await admin.get("/api/audit", params={"action": "peer.share_used"})).json()
    assert audit["total"] == 2


async def test_share_rate_limit(client: AsyncClient, admin: Session) -> None:
    for _ in range(20):
        assert (await client.get("/api/share/nothing")).status_code == 404
    r = await client.get("/api/share/nothing")
    assert r.status_code == 429
