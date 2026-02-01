from pydantic import BaseModel, field_validator
import re
from app.config import get_settings

settings = get_settings()


class InterfaceCreate(BaseModel):
    name: str
    listen_port: int
    address: str
    dns: str | None = None
    post_up: str | None = None
    post_down: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Interface name must be alphanumeric (with _ or -)")
        if len(v) > 15:
            raise ValueError("Interface name must be 15 characters or less")
        return v

    @field_validator("listen_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("Listen port must be between 1 and 65535")
        return v

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        # Split by comma (multiple addresses allowed)
        for addr in v.split(","):
            addr = addr.strip()
            # Basic CIDR check (IPv4 or IPv6)
            # This regex prevents newlines and dangerous shell chars
            if not re.match(r"^[a-fA-F0-9\.:]+/\d+$", addr):
                raise ValueError(f"Invalid address format: {addr}. Must be CIDR (e.g. 10.0.0.1/24)")
        return v

    @field_validator("dns")
    @classmethod
    def validate_dns(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        for item in v.split(","):
            item = item.strip()
            # Allow IPs or Hostnames
            # Hostnames: alphanum, dots, dashes
            # IPs: alphanum, dots, colons
            if not re.match(r"^[a-zA-Z0-9\.\-\:]+$", item):
                 raise ValueError(f"Invalid DNS entry: {item}")
        return v

    @field_validator("post_up", "post_down")
    @classmethod
    def validate_post_commands(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v

        # Check if custom scripts are allowed
        if not settings.wg_allow_custom_scripts:
            # Only allow iptables commands (common use case)
            allowed_patterns = [
                r"^iptables\s+-[A-Z]\s+\w+",
                r"^ip6tables\s+-[A-Z]\s+\w+",
            ]
            if not any(re.match(pattern, v) for pattern in allowed_patterns):
                raise ValueError(
                    "Custom PostUp/PostDown commands are disabled. "
                    "Set WG_ALLOW_CUSTOM_SCRIPTS=true to enable (security risk)."
                )

        # Detect obviously dangerous patterns
        dangerous = [";", "&&", "||", "|", "`", "$", "$(", "curl", "wget", "nc", "bash", "sh"]
        if any(danger in v for danger in dangerous):
            raise ValueError(
                f"Potentially dangerous command detected in PostUp/PostDown. "
                f"Blocked characters/commands: {', '.join(dangerous)}"
            )

        return v


class InterfaceUpdate(BaseModel):
    listen_port: int | None = None
    address: str | None = None
    dns: str | None = None
    post_up: str | None = None
    post_down: str | None = None

    @field_validator("listen_port")
    @classmethod
    def validate_port(cls, v: int | None) -> int | None:
        if v is not None and not 1 <= v <= 65535:
            raise ValueError("Listen port must be between 1 and 65535")
        return v

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Split by comma (multiple addresses allowed)
        for addr in v.split(","):
            addr = addr.strip()
            # Basic CIDR check (IPv4 or IPv6)
            # This regex prevents newlines and dangerous shell chars
            if not re.match(r"^[a-fA-F0-9\.:]+/\d+$", addr):
                raise ValueError(f"Invalid address format: {addr}. Must be CIDR (e.g. 10.0.0.1/24)")
        return v

    @field_validator("dns")
    @classmethod
    def validate_dns(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        for item in v.split(","):
            item = item.strip()
            # Allow IPs or Hostnames
            # Hostnames: alphanum, dots, dashes
            # IPs: alphanum, dots, colons
            if not re.match(r"^[a-zA-Z0-9\.\-\:]+$", item):
                 raise ValueError(f"Invalid DNS entry: {item}")
        return v

    @field_validator("post_up", "post_down")
    @classmethod
    def validate_post_commands(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v

        # Check if custom scripts are allowed
        if not settings.wg_allow_custom_scripts:
            # Only allow iptables commands (common use case)
            allowed_patterns = [
                r"^iptables\s+-[A-Z]\s+\w+",
                r"^ip6tables\s+-[A-Z]\s+\w+",
            ]
            if not any(re.match(pattern, v) for pattern in allowed_patterns):
                raise ValueError(
                    "Custom PostUp/PostDown commands are disabled. "
                    "Set WG_ALLOW_CUSTOM_SCRIPTS=true to enable (security risk)."
                )

        # Detect obviously dangerous patterns
        dangerous = [";", "&&", "||", "|", "`", "$", "$(", "curl", "wget", "nc", "bash", "sh"]
        if any(danger in v for danger in dangerous):
            raise ValueError(
                f"Potentially dangerous command detected in PostUp/PostDown. "
                f"Blocked characters/commands: {', '.join(dangerous)}"
            )

        return v


class InterfaceResponse(BaseModel):
    name: str
    listen_port: int
    address: str
    public_key: str
    is_active: bool
    peer_count: int
    active_peer_count: int  # Peers with recent handshake (< 3 minutes)
    total_transfer_rx: int
    total_transfer_tx: int
    dns: str | None = None
    post_up: str | None = None
    post_down: str | None = None
