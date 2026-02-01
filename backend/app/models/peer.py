from pydantic import BaseModel, field_validator
from datetime import datetime
import re


class PeerCreate(BaseModel):
    name: str
    allowed_ips: str
    persistent_keepalive: int = 25

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_\- ]+$", v):
            raise ValueError("Peer name must be alphanumeric (with _, -, or space)")
        if len(v) > 64:
            raise ValueError("Peer name must be 64 characters or less")
        return v

    @field_validator("persistent_keepalive")
    @classmethod
    def validate_keepalive(cls, v: int) -> int:
        if not 0 <= v <= 65535:
            raise ValueError("Persistent keepalive must be between 0 and 65535")
        return v


class PeerUpdate(BaseModel):
    name: str | None = None
    allowed_ips: str | None = None
    persistent_keepalive: int | None = None


class PeerResponse(BaseModel):
    name: str
    public_key: str
    allowed_ips: str
    endpoint: str | None = None
    latest_handshake: datetime | None = None
    transfer_rx: int = 0
    transfer_tx: int = 0
    is_online: bool = False
    persistent_keepalive: int = 0
