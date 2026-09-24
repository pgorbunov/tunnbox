"""Runtime settings schemas."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.common import ApiModel, normalize_cidr_list, normalize_ip_list, validate_endpoint_host, validate_mtu


class SettingsResponse(ApiModel):
    public_endpoint: str
    default_dns: str
    default_mtu: int | None
    default_keepalive: int
    default_client_allowed_ips: str
    audit_retention_days: int
    stats_retention_days: int
    ui_refresh_seconds: int
    custom_scripts_allowed: bool


class SettingsUpdate(ApiModel):
    public_endpoint: str | None = None
    default_dns: str | None = None
    default_mtu: int | None = None
    default_keepalive: int | None = Field(default=None, ge=0, le=65535)
    default_client_allowed_ips: str | None = None
    audit_retention_days: int | None = Field(default=None, ge=1, le=3650)
    stats_retention_days: int | None = Field(default=None, ge=1, le=3650)
    ui_refresh_seconds: int | None = Field(default=None, ge=2, le=3600)

    @field_validator("public_endpoint")
    @classmethod
    def _endpoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_endpoint_host(value) or ""

    @field_validator("default_dns")
    @classmethod
    def _dns(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_ip_list(value) or ""

    @field_validator("default_mtu")
    @classmethod
    def _mtu(cls, value: int | None) -> int | None:
        return validate_mtu(value)

    @field_validator("default_client_allowed_ips")
    @classmethod
    def _allowed(cls, value: str | None) -> str | None:
        return normalize_cidr_list(value) if value is not None else None
