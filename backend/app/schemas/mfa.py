"""MFA schemas."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel


class MfaSetupResponse(ApiModel):
    secret: str
    otpauth_uri: str
    qr_svg: str


class MfaSetupRequest(ApiModel):
    password: str = Field(min_length=1, max_length=128)


class MfaEnableRequest(ApiModel):
    code: str = Field(min_length=6, max_length=8)
    password: str = Field(min_length=1, max_length=128)


class MfaDisableRequest(ApiModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=1, max_length=32)


class MfaPasswordRequest(ApiModel):
    password: str = Field(min_length=1, max_length=128)


class RecoveryCodes(ApiModel):
    recovery_codes: list[str]
