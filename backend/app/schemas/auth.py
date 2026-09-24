"""Auth schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.users import User


class AuthStatus(ApiModel):
    setup_required: bool
    version: str


class SetupRequest(ApiModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._@-]+$")
    password: str = Field(min_length=1, max_length=128)


class LoginRequest(ApiModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class MfaLoginRequest(ApiModel):
    mfa_token: str
    code: str = Field(min_length=1, max_length=32)


class LoginSuccess(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: User


class MfaRequired(ApiModel):
    mfa_required: Literal[True] = True
    mfa_token: str


class RefreshResponse(ApiModel):
    access_token: str
    expires_in: int
    user: User


class PasswordChange(ApiModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class Session(ApiModel):
    id: str
    ip: str | None
    user_agent: str | None
    created_at: str
    last_used_at: str
    expires_at: str
    current: bool
