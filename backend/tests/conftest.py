"""Shared fixtures: each test gets a fresh app with its own temp DB and config dir (mock backend)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app

ADMIN = {"username": "admin", "password": "correct-horse-battery"}


def make_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    env = {
        "DATABASE_PATH": str(tmp_path / "tunnbox.db"),
        "DATABASE_URL": "",
        "WG_CONFIG_PATH": str(tmp_path / "wireguard"),
        "WG_BACKEND_MODE": "mock",
        "SECRET_KEY": "test-secret-key-do-not-use",
        "BCRYPT_ROUNDS": "4",
        "WG_ALLOW_CUSTOM_SCRIPTS": "false",
        "WG_DEFAULT_ENDPOINT": "vpn.example.com",
        "LOGIN_RATE_LIMIT": "100/minute",
        "LOCKOUT_THRESHOLD": "3",
        "STATS_SAMPLE_SECONDS": "3600",
        **overrides,
    }
    for key, value in env.items():
        if value == "":
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    get_settings.cache_clear()


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_env(tmp_path, monkeypatch)
    return tmp_path


@pytest.fixture
async def app(env: Path) -> AsyncIterator[FastAPI]:
    application = create_app()
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


class Session:
    """An authenticated user for tests: carries the bearer header and cookie jar."""

    def __init__(self, client: AsyncClient, token: str, user: dict[str, Any]) -> None:
        self.client = client
        self.token = token
        self.user = user

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def get(self, url: str, **kw: Any):  # noqa: ANN201
        return await self.client.get(url, headers=self.headers, **kw)

    async def post(self, url: str, **kw: Any):  # noqa: ANN201
        return await self.client.post(url, headers=self.headers, **kw)

    async def patch(self, url: str, **kw: Any):  # noqa: ANN201
        return await self.client.patch(url, headers=self.headers, **kw)

    async def delete(self, url: str, **kw: Any):  # noqa: ANN201
        return await self.client.delete(url, headers=self.headers, **kw)


async def do_setup(client: AsyncClient) -> Session:
    r = await client.post("/api/auth/setup", json=ADMIN)
    assert r.status_code == 200, r.text
    body = r.json()
    return Session(client, body["access_token"], body["user"])


async def do_login(client: AsyncClient, username: str, password: str) -> Session:
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return Session(client, body["access_token"], body["user"])


@pytest.fixture
async def admin(client: AsyncClient) -> Session:
    return await do_setup(client)


async def create_user(admin: Session, username: str, role: str, password: str = "another-strong-pass") -> Session:
    r = await admin.post("/api/users", json={"username": username, "password": password, "role": role})
    assert r.status_code == 201, r.text
    return await do_login(admin.client, username, password)


async def create_interface(admin: Session, name: str = "wg0", address: str = "10.8.0.1/24", port: int = 51820, **extra: Any) -> dict[str, Any]:
    r = await admin.post("/api/interfaces", json={"name": name, "address": address, "listen_port": port, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def create_peer(admin: Session, iface: str = "wg0", name: str = "laptop", **extra: Any) -> dict[str, Any]:
    r = await admin.post(f"/api/interfaces/{iface}/peers", json={"name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def conf_text(env: Path, name: str = "wg0") -> str:
    return (env / "wireguard" / f"{name}.conf").read_text()


def ctx_of(app: FastAPI):  # noqa: ANN201
    return app.state.ctx


__all__ = ["os"]
