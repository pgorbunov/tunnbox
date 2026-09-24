"""Interface schemas."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.common import (
    ApiModel,
    normalize_cidr_list,
    normalize_ip_list,
    validate_endpoint_host,
    validate_interface_name,
    validate_mtu,
)


class Interface(ApiModel):
    id: int
    name: str
    public_key: str
    address: str
    listen_port: int
    dns: str | None
    mtu: int | None
    post_up: str | None
    post_down: str | None
    public_endpoint: str | None
    enabled: bool
    is_active: bool
    peer_count: int
    online_peer_count: int
    rx_total: int
    tx_total: int
    created_at: str
    updated_at: str


class _InterfaceFields(ApiModel):
    @field_validator("dns", check_fields=False)
    @classmethod
    def _dns(cls, value: str | None) -> str | None:
        return normalize_ip_list(value)

    @field_validator("mtu", check_fields=False)
    @classmethod
    def _mtu(cls, value: int | None) -> int | None:
        return validate_mtu(value)

    @field_validator("public_endpoint", check_fields=False)
    @classmethod
    def _endpoint(cls, value: str | None) -> str | None:
        return validate_endpoint_host(value)

    @field_validator("post_up", "post_down", check_fields=False)
    @classmethod
    def _scripts(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            return None
        return value


class InterfaceCreate(_InterfaceFields):
    name: str
    address: str
    listen_port: int = Field(ge=1, le=65535)
    dns: str | None = None
    mtu: int | None = None
    post_up: str | None = Field(default=None, max_length=4000)
    post_down: str | None = Field(default=None, max_length=4000)
    public_endpoint: str | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return validate_interface_name(value)

    @field_validator("address")
    @classmethod
    def _address(cls, value: str) -> str:
        return normalize_cidr_list(value)


class InterfaceUpdate(_InterfaceFields):
    address: str | None = None
    listen_port: int | None = Field(default=None, ge=1, le=65535)
    dns: str | None = None
    mtu: int | None = None
    post_up: str | None = Field(default=None, max_length=4000)
    post_down: str | None = Field(default=None, max_length=4000)
    public_endpoint: str | None = None
    enabled: bool | None = None

    @field_validator("address")
    @classmethod
    def _address(cls, value: str | None) -> str | None:
        return normalize_cidr_list(value) if value is not None else None
