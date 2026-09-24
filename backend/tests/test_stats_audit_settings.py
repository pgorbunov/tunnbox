"""Stats sampler + overview, audit query/export, settings validation, system endpoints."""

from __future__ import annotations

import io
import tarfile

from httpx import AsyncClient

from app.services import stats as stats_service
from tests.conftest import Session, create_interface, create_peer


async def test_sampler_writes_rows_and_stats_respond(client: AsyncClient, admin: Session, app) -> None:  # noqa: ANN001
    await create_interface(admin)
    peers = [await create_peer(admin, name=f"p{i}") for i in range(6)]
    ctx = app.state.ctx
    written = await stats_service.sample(ctx)
    assert written == 6  # first sample per peer always recorded
    await stats_service.sample(ctx)
    listed = (await admin.get("/api/interfaces/wg0/peers")).json()
    assert any(p["rx_total"] > 0 for p in listed)
    assert any(p["is_online"] and p["latest_handshake_at"] and p["endpoint"] for p in listed)
    assert any(p["status"] == "online" for p in listed)
    iface = (await admin.get("/api/interfaces/wg0")).json()
    assert iface["rx_total"] > 0 and iface["online_peer_count"] >= 1
    r = await admin.get("/api/interfaces/wg0/stats", params={"range": "1h"})
    body = r.json()
    assert body["range"] == "1h" and body["bucket_seconds"] == 60 and body["points"]
    assert body["rx_total"] == iface["rx_total"]
    r = await admin.get(f"/api/peers/{peers[0]['id']}/stats", params={"range": "7d"})
    assert r.status_code == 200 and r.json()["bucket_seconds"] == 3600
    assert (await admin.get("/api/interfaces/wg0/stats", params={"range": "bogus"})).status_code == 422
    overview = (await admin.get("/api/stats/overview")).json()
    assert overview["interfaces_total"] == 1 and overview["interfaces_active"] == 1
    assert overview["peers_total"] == 6 and overview["peers_online"] >= 1
    assert overview["rx_total"] > 0 and overview["series"] and len(overview["top_peers"]) == 5
    assert 8 <= len(overview["recent_activity"]) <= 10
    # counters are monotonic across samples
    before = {p["id"]: p["rx_total"] for p in listed}
    await stats_service.sample(ctx)
    after = {p["id"]: p["rx_total"] for p in (await admin.get("/api/interfaces/wg0/peers")).json()}
    assert all(after[i] >= before[i] for i in before)


async def test_retention_job_runs(client: AsyncClient, admin: Session, app) -> None:  # noqa: ANN001
    removed = await stats_service.retention(app.state.ctx)
    assert set(removed) == {"audit", "stats", "sessions", "share_links"}


async def test_audit_query_and_export(client: AsyncClient, admin: Session) -> None:
    await create_interface(admin)
    await create_peer(admin)
    r = await admin.get("/api/audit", params={"page_size": 2})
    body = r.json()
    assert body["total"] >= 3 and len(body["items"]) == 2 and body["page_size"] == 2
    entry = body["items"][0]
    assert set(entry) == {"id", "user_id", "username", "action", "target", "details", "ip", "created_at"}
    r = await admin.get("/api/audit", params={"username": "admin", "q": "wg0"})
    assert all("wg0" in (e["target"] or "") or "wg0" in str(e["details"]) for e in r.json()["items"])
    r = await admin.get("/api/audit", params={"from": "2100-01-01T00:00:00Z"})
    assert r.json()["total"] == 0
    r = await admin.get("/api/audit/export.csv", params={"action": "peer.created"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,created_at,username") and len(lines) == 2 and "peer.created" in lines[1]


async def test_settings_get_and_validation(client: AsyncClient, admin: Session) -> None:
    r = await admin.get("/api/settings")
    body = r.json()
    assert body["public_endpoint"] == "vpn.example.com" and body["default_dns"] == "1.1.1.1"
    assert body["default_mtu"] is None and body["default_keepalive"] == 25 and body["ui_refresh_seconds"] == 10
    assert body["custom_scripts_allowed"] is False
    for bad in (
        {"public_endpoint": "host:1234"},
        {"default_dns": "1.1.1.1, nope"},
        {"default_mtu": 900},
        {"default_client_allowed_ips": "x"},
        {"ui_refresh_seconds": 0},
        {"unknown": 1},
    ):
        r = await admin.patch("/api/settings", json=bad)
        assert r.status_code == 422, bad
    r = await admin.patch("/api/settings", json={"public_endpoint": "10.0.0.1", "default_mtu": 1400, "default_dns": "9.9.9.9", "default_keepalive": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["public_endpoint"] == "10.0.0.1" and body["default_mtu"] == 1400 and body["default_keepalive"] == 0
    await create_interface(admin)
    peer = await create_peer(admin)
    text = (await admin.get(f"/api/peers/{peer['id']}/config")).text
    assert "Endpoint = 10.0.0.1:51820" in text and "MTU = 1400" in text and "DNS = 9.9.9.9" in text and "PersistentKeepalive" not in text
    assert (await admin.get("/api/audit", params={"action": "settings.updated"})).json()["total"] == 1


async def test_system_endpoints(client: AsyncClient, admin: Session) -> None:
    assert (await client.get("/api/health")).json() == {"status": "ok"}
    assert (await client.get("/api/system/health")).json() == {"status": "ok"}
    info = (await admin.get("/api/system/info")).json()
    assert info["backend_mode"] == "mock" and info["version"] == "2.0.0" and info["database_size_bytes"] > 0
    await create_interface(admin)
    r = await admin.get("/api/system/backup")
    assert r.status_code == 200 and r.headers["content-type"] == "application/gzip"
    with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:gz") as tar:
        assert {"tunnbox.db", "wireguard/wg0.conf"} <= set(tar.getnames())
    r = await admin.get("/api/system/export")
    data = r.json()
    assert set(data) == {"metadata", "users", "interfaces", "peers", "settings", "audit_logs"}
    assert "password_hash" not in data["users"][0] and "private_key_enc" not in data["interfaces"][0]
    actions = set((await admin.get("/api/audit/actions")).json())
    assert {"system.backup", "system.export"} <= actions
