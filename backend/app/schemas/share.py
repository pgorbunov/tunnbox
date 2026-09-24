"""Public share link schemas."""

from __future__ import annotations

from app.schemas.common import ApiModel


class SharePayload(ApiModel):
    peer_name: str
    interface_name: str
    expires_at: str
    remaining_uses: int
    config: str
    qr_png_base64: str
