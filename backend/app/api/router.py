"""Mount every router under /api."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import api_keys, audit, auth, interfaces, mfa, peers, sessions, settings, share, stats, system, users
from app.schemas.system import Health

api_router = APIRouter(prefix="/api")


@api_router.get("/health", response_model=Health, tags=["system"])
async def health() -> Health:
    return Health()


for module in (auth, sessions, mfa, api_keys, users, interfaces, peers, share, stats, audit, settings, system):
    api_router.include_router(module.router)
