"""API key schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ApiModel

Scope = Literal["read", "peers:write", "interfaces:write", "admin"]


class ApiKey(ApiModel):
    id: int
    name: str
    prefix: str
    scopes: list[str]
    expires_at: str | None
    last_used_at: str | None
    created_at: str
    revoked_at: str | None


class ApiKeyCreated(ApiKey):
    key: str


class ApiKeyCreate(ApiModel):
    name: str = Field(min_length=1, max_length=64)
    scopes: list[Scope] = Field(min_length=1)
    expires_at: str | None = None

    @field_validator("scopes")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        return sorted(set(value))
