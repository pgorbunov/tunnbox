"""Security headers, CSP and error shapes."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

from app.core.csp import build_app_csp, inline_script_hashes


async def test_security_headers_and_csp(client: AsyncClient) -> None:
    r = await client.get("/api/health")
    h = r.headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert h["cross-origin-opener-policy"] == "same-origin" and h["cross-origin-resource-policy"] == "same-origin"
    assert "camera=()" in h["permissions-policy"]
    csp = h["content-security-policy"]
    script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src"))
    assert "'unsafe-inline'" not in script_src and "'self'" in script_src
    assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
    assert "strict-transport-security" not in h
    docs = await client.get("/api/docs")
    assert "cdn.jsdelivr.net" in docs.headers["content-security-policy"]


def test_inline_script_hashes(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text('<html><head><script src="/x.js"></script></head><body><script>{console.log(1)}</script></body></html>')
    hashes = inline_script_hashes(index)
    assert len(hashes) == 1 and hashes[0].startswith("'sha256-")
    csp = build_app_csp(hashes)
    assert f"script-src 'self' {hashes[0]}" in csp and "'unsafe-inline'" not in csp.split("style-src")[0]
    assert inline_script_hashes(tmp_path / "missing.html") == []


async def test_error_shapes(client: AsyncClient) -> None:
    r = await client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}
    r = await client.post("/api/auth/login", json={"username": "x"})
    assert r.status_code == 422 and isinstance(r.json()["detail"], str) and r.json()["code"] == "validation_error"
    r = await client.post("/api/auth/login", json={"username": "x", "password": "y-password-1"})
    assert r.json()["code"] == "unauthorized"


async def test_spa_fallback_and_hashed_inline_script(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    from httpx import ASGITransport

    from app import main as main_module
    from tests.conftest import make_env

    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text("<html><body><script>window.__boot = 1;</script></body></html>")
    (build / "app.js").write_text("console.log('x')")
    make_env(tmp_path, monkeypatch)
    monkeypatch.setattr(main_module, "FRONTEND_BUILD", build)
    app = main_module.create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            r = await c.get("/")
            assert r.status_code == 200 and "__boot" in r.text
            r = await c.get("/app.js")
            assert r.status_code == 200 and r.text.startswith("console")
            r = await c.get("/interfaces/wg0")  # client-side route -> index.html
            assert r.status_code == 200 and "__boot" in r.text
            r = await c.get("/api/nope")
            assert r.status_code == 404 and r.json()["detail"] == "Not Found"
            csp = r.headers["content-security-policy"]
            expected = inline_script_hashes(build / "index.html")[0]
            assert expected in csp and "'unsafe-inline'" not in csp.split("style-src")[0]
