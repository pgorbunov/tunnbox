"""Shared schema pieces and validators."""

from __future__ import annotations

import ipaddress
import re
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

Role = Literal["admin", "operator", "viewer"]
ROLE_RANK: dict[str, int] = {"viewer": 1, "operator": 2, "admin": 3}

INTERFACE_NAME_RE = re.compile(r"^[a-zA-Z0-9_=+.-]{1,15}$")
RESERVED_INTERFACE_NAMES = frozenset({"all", "default", "lo"})
HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
)

T = TypeVar("T")


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


def validate_interface_name(name: str) -> str:
    if not INTERFACE_NAME_RE.match(name) or name.lower() in RESERVED_INTERFACE_NAMES or ".." in name:
        raise ValueError("Invalid interface name")
    return name


def normalize_cidr_list(value: str, *, host_only: bool = False) -> str:
    """Validate a comma separated list of CIDRs and normalise spacing."""
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        raise ValueError("At least one address is required")
    out: list[str] = []
    for part in parts:
        try:
            iface = ipaddress.ip_interface(part)
        except ValueError as exc:
            raise ValueError(f"Invalid address: {part}") from exc
        if host_only and "/" not in part:
            part = f"{iface.ip}/{iface.max_prefixlen}"
        out.append(part if "/" in part else f"{iface.ip}/{iface.max_prefixlen}")
    return ", ".join(out)


def normalize_ip_list(value: str | None) -> str | None:
    """Validate a comma separated list of IP addresses (DNS servers)."""
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        return None
    for part in parts:
        try:
            ipaddress.ip_address(part)
        except ValueError as exc:
            raise ValueError(f"Invalid IP address: {part}") from exc
    return ", ".join(parts)


def validate_endpoint_host(value: str | None) -> str | None:
    """Hostname or IP without port; empty -> None."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    if HOSTNAME_RE.match(value):
        return value.rstrip(".")
    raise ValueError("Endpoint must be a hostname or IP address without a port")


def validate_mtu(value: int | None) -> int | None:
    if value is not None and not 1280 <= value <= 1500:
        raise ValueError("MTU must be between 1280 and 1500")
    return value
