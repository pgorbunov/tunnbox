"""Peer schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ApiModel, normalize_cidr_list, normalize_ip_list

PeerStatus = Literal["online", "offline", "disabled", "expired"]


class Peer(ApiModel):
    id: int
    interface_id: int
    interface_name: str
    name: str
    public_key: str
    allowed_ips: str
    client_allowed_ips: str
    client_dns: str | None
    persistent_keepalive: int
    enabled: bool
    expires_at: str | None
    notes: str | None
    has_private_key: bool
    has_preshared_key: bool
    endpoint: str | None
    latest_handshake_at: str | None
    is_online: bool
    rx_total: int
    tx_total: int
    created_at: str
    updated_at: str
    status: PeerStatus


class _PeerFields(ApiModel):
    @field_validator("client_allowed_ips", check_fields=False)
    @classmethod
    def _client_allowed(cls, value: str | None) -> str | None:
        return normalize_cidr_list(value) if value is not None else None

    @field_validator("client_dns", check_fields=False)
    @classmethod
    def _dns(cls, value: str | None) -> str | None:
        return normalize_ip_list(value)

    @field_validator("expires_at", check_fields=False)
    @classmethod
    def _expires(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        from app.core.security import iso, parse_iso

        try:
            parsed = parse_iso(value)
        except ValueError as exc:
            raise ValueError("expires_at must be an ISO-8601 datetime") from exc
        assert parsed is not None
        return iso(parsed)


class PeerCreate(_PeerFields):
    name: str = Field(min_length=1, max_length=64)
    allowed_ips: str | None = None  # "auto" or CIDR list
    client_allowed_ips: str | None = None
    client_dns: str | None = None
    persistent_keepalive: int | None = Field(default=None, ge=0, le=65535)
    expires_at: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    enabled: bool = True

    @field_validator("allowed_ips")
    @classmethod
    def _allowed(cls, value: str | None) -> str | None:
        if value is None or value.strip().lower() in {"", "auto"}:
            return None
        return normalize_cidr_list(value, host_only=True)


class PeerUpdate(_PeerFields):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    allowed_ips: str | None = None
    client_allowed_ips: str | None = None
    client_dns: str | None = None
    persistent_keepalive: int | None = Field(default=None, ge=0, le=65535)
    expires_at: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None

    @field_validator("allowed_ips")
    @classmethod
    def _allowed(cls, value: str | None) -> str | None:
        return normalize_cidr_list(value, host_only=True) if value is not None else None


class NextIp(ApiModel):
    allowed_ips: str


class BulkRequest(ApiModel):
    ids: list[int] = Field(min_length=1, max_length=1000)
    action: Literal["enable", "disable", "delete"]


class BulkResult(ApiModel):
    affected: int


class ShareCreate(ApiModel):
    expires_in_hours: int = Field(default=24, ge=1, le=24 * 30)
    max_uses: int = Field(default=1, ge=1, le=100)


class ShareCreated(ApiModel):
    url_path: str
    token: str
    expires_at: str
    max_uses: int
