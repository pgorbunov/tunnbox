"""User schemas."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel, Role


class User(ApiModel):
    id: int
    username: str
    role: Role
    is_active: bool
    totp_enabled: bool
    last_login_at: str | None
    created_at: str


class UserCreate(ApiModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._@-]+$")
    password: str = Field(min_length=1, max_length=128)
    role: Role = "viewer"


class UserUpdate(ApiModel):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=1, max_length=128)
