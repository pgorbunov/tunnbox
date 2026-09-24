"""Interface CRUD, rendering, up/down and validation."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

from tests.conftest import Session, conf_text, create_interface, create_peer


async def test_interface_crud_and_rendering(client: AsyncClient, admin: Session, env: Path) -> None:
    iface = await create_interface(admin, dns="1.1.1.1, 8.8.8.8", mtu=1420, public_endpoint="vpn.example.org")
    assert iface["name"] == "wg0" and iface["enabled"] and iface["is_active"] and iface["peer_count"] == 0
    assert len(iface["public_key"]) == 44
    conf = conf_text(env)
    assert "PrivateKey = " in conf and "ListenPort = 51820" in conf and "MTU = 1420" in conf
    assert "DNS = 1.1.1.1, 8.8.8.8" in conf and "# PublicEndpoint = vpn.example.org" in conf
    assert oct((env / "wireguard" / "wg0.conf").stat().st_mode & 0o777) == "0o600"

    listed = (await admin.get("/api/interfaces")).json()
    assert [i["name"] for i in listed] == ["wg0"]
    assert (await admin.get("/api/interfaces/wg0")).json()["listen_port"] == 51820
    assert (await admin.get("/api/interfaces/nope")).status_code == 404

    r = await admin.patch("/api/interfaces/wg0", json={"listen_port": 51830, "dns": None})
    assert r.status_code == 200 and r.json()["listen_port"] == 51830 and r.json()["dns"] is None
    conf = conf_text(env)
    assert "ListenPort = 51830" in conf and "DNS" not in conf

    r = await admin.post("/api/interfaces/wg0/down")
    assert r.json()["is_active"] is False and r.json()["enabled"] is False
    r = await admin.post("/api/interfaces/wg0/up")
    assert r.json()["is_active"] is True and r.json()["enabled"] is True
    r = await admin.patch("/api/interfaces/wg0", json={"enabled": False})
    assert r.json()["is_active"] is False

    server_conf = await admin.get("/api/interfaces/wg0/config")
    assert server_conf.status_code == 200 and server_conf.text == conf_text(env)

    await create_peer(admin)
    assert (await admin.delete("/api/interfaces/wg0")).status_code == 204
    assert not (env / "wireguard" / "wg0.conf").exists()
    assert (await admin.get("/api/peers")).json()["total"] == 0
    actions = set((await admin.get("/api/audit/actions")).json())
    assert {"interface.created", "interface.updated", "interface.up", "interface.down", "interface.deleted"} <= actions


async def test_interface_validation(client: AsyncClient, admin: Session) -> None:
    bad = [
        {"name": "lo", "address": "10.8.0.1/24", "listen_port": 51820},
        {"name": "../etc", "address": "10.8.0.1/24", "listen_port": 51820},
        {"name": "toolongname123456", "address": "10.8.0.1/24", "listen_port": 51820},
        {"name": "wg0", "address": "not-an-ip", "listen_port": 51820},
        {"name": "wg0", "address": "10.8.0.1/24", "listen_port": 70000},
        {"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820, "mtu": 100},
        {"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820, "public_endpoint": "host:51820"},
        {"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820, "dns": "not-dns"},
    ]
    for payload in bad:
        r = await admin.post("/api/interfaces", json=payload)
        assert r.status_code == 422, payload
        assert isinstance(r.json()["detail"], str)
    r = await admin.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820, "post_up": "iptables -A"})
    assert r.status_code == 400
    await create_interface(admin)
    r = await admin.post("/api/interfaces", json={"name": "wg0", "address": "10.9.0.1/24", "listen_port": 51821})
    assert r.status_code == 409
    r = await admin.post("/api/interfaces", json={"name": "wg1", "address": "10.9.0.1/24", "listen_port": 51820})
    assert r.status_code == 409


async def test_custom_scripts_when_allowed(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    from httpx import ASGITransport

    from app.main import create_app
    from tests.conftest import do_setup, make_env

    make_env(tmp_path, monkeypatch, WG_ALLOW_CUSTOM_SCRIPTS="true")
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            admin = await do_setup(c)
            r = await admin.post("/api/interfaces", json={"name": "wg0", "address": "10.8.0.1/24", "listen_port": 51820, "post_up": "echo up", "post_down": "echo down"})
            assert r.status_code == 201
            assert "PostUp = echo up" in (tmp_path / "wireguard" / "wg0.conf").read_text()
            assert (await admin.get("/api/settings")).json()["custom_scripts_allowed"] is True
