"""One-time share links for peer onboarding."""

from __future__ import annotations

import base64
from datetime import timedelta
from typing import Any

from app.context import AppContext
from app.core.errors import Gone, NotFound
from app.core.security import iso, new_opaque_token, now_iso, sha256_hex, utcnow
from app.db.connection import connect
from app.db.repos import peers as peers_repo
from app.db.repos import share_links as repo
from app.services import audit, peers


async def create_link(ctx: AppContext, actor: audit.Actor, peer_id: int, expires_in_hours: int, max_uses: int) -> dict[str, Any]:
    token = new_opaque_token(32)
    expires_at = iso(utcnow() + timedelta(hours=expires_in_hours))
    async with connect(ctx.db_path) as db:
        row = await peers_repo.get(db, peer_id)
        if row is None:
            raise NotFound("Peer not found")
        if not row["private_key_enc"]:
            raise NotFound("No private key stored for this peer")
        await repo.create(
            db,
            peer_id=peer_id,
            token_hash=sha256_hex(token),
            created_by=actor.user_id,
            expires_at=expires_at,
            max_uses=max_uses,
            now=now_iso(),
        )
        await audit.add(db, actor, "peer.share_created", target=f"{row['interface_name']}/{row['name']}", details={"peer_id": peer_id, "expires_at": expires_at, "max_uses": max_uses})
    return {"url_path": f"/share/{token}", "token": token, "expires_at": expires_at, "max_uses": max_uses}


async def redeem(ctx: AppContext, token: str, ip: str | None) -> dict[str, Any]:
    """Consume one use of the link and return the peer's config + QR."""
    now = now_iso()
    async with connect(ctx.db_path) as db:
        link = await repo.get_by_token_hash(db, sha256_hex(token))
        if link is None:
            raise NotFound("Share link not found")
        if link["expires_at"] <= now:
            raise Gone("Share link has expired", code="expired")
        if link["uses"] >= link["max_uses"]:
            raise Gone("Share link has already been used", code="exhausted")
        await repo.record_use(db, link["id"], now)
        remaining = link["max_uses"] - link["uses"] - 1
        peer_id = link["peer_id"]
    config, row = await peers.client_config(ctx, peer_id)
    async with connect(ctx.db_path) as db:
        await audit.add(db, audit.Actor(user_id=None, username="anonymous", ip=ip), "peer.share_used", target=f"{row['interface_name']}/{row['name']}", details={"peer_id": peer_id, "remaining_uses": remaining})
    return {
        "peer_name": row["name"],
        "interface_name": row["interface_name"],
        "expires_at": link["expires_at"],
        "remaining_uses": remaining,
        "config": config,
        "qr_png_base64": base64.b64encode(peers.qr_png(config)).decode(),
    }
