"""/api/peers — peer search, details, actions, client config, QR, share, stats, bulk."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import PlainTextResponse

from app.api.deps import Ctx, require
from app.core.errors import ValidationFailed
from app.schemas.common import Page, normalize_cidr_list
from app.schemas.peers import BulkRequest, BulkResult, Peer, PeerUpdate, ShareCreate, ShareCreated
from app.schemas.stats import StatsRange, StatsSeries
from app.services import peers as service
from app.services import share as share_service
from app.services import stats as stats_service
from app.services.auth import Principal

router = APIRouter(prefix="/peers", tags=["peers"])
Reader = Annotated[Principal, Depends(require("viewer", "read"))]
Writer = Annotated[Principal, Depends(require("operator", "peers:write"))]


def _override(allowed_ips: str | None) -> str | None:
    if allowed_ips is None or not allowed_ips.strip():
        return None
    try:
        return normalize_cidr_list(allowed_ips)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc


def _filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "peer"
    return f"{safe[:60]}.conf"


@router.get("", response_model=Page[Peer])
async def search_peers(
    _: Reader,
    ctx: Ctx,
    q: str | None = Query(default=None, max_length=200),
    interface: str | None = Query(default=None, max_length=15),
    status: str | None = Query(default=None, pattern="^(online|offline|disabled|expired)$"),  # noqa: A002
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> Page[Peer]:
    items, total = await service.search(ctx, q=q, interface=interface, status=status, page=page, page_size=page_size)
    return Page[Peer](items=[Peer(**p) for p in items], total=total, page=page, page_size=page_size)


@router.post("/bulk", response_model=BulkResult)
async def bulk(body: BulkRequest, principal: Writer, ctx: Ctx) -> BulkResult:
    return BulkResult(affected=await service.bulk(ctx, principal.actor, body.ids, body.action))


@router.get("/{peer_id}", response_model=Peer)
async def get_peer(peer_id: int, _: Reader, ctx: Ctx) -> Peer:
    return Peer(**await service.get_peer(ctx, peer_id))


@router.patch("/{peer_id}", response_model=Peer)
async def update_peer(peer_id: int, body: PeerUpdate, principal: Writer, ctx: Ctx) -> Peer:
    return Peer(**await service.update_peer(ctx, principal.actor, peer_id, body, is_admin=principal.role == "admin"))


@router.delete("/{peer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_peer(peer_id: int, principal: Writer, ctx: Ctx) -> Response:
    await service.delete_peer(ctx, principal.actor, peer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{peer_id}/enable", response_model=Peer)
async def enable_peer(peer_id: int, principal: Writer, ctx: Ctx) -> Peer:
    return Peer(**await service.set_enabled(ctx, principal.actor, peer_id, True))


@router.post("/{peer_id}/disable", response_model=Peer)
async def disable_peer(peer_id: int, principal: Writer, ctx: Ctx) -> Peer:
    return Peer(**await service.set_enabled(ctx, principal.actor, peer_id, False))


@router.post("/{peer_id}/rotate-keys", response_model=Peer)
async def rotate_keys(peer_id: int, principal: Writer, ctx: Ctx) -> Peer:
    return Peer(**await service.rotate_keys(ctx, principal.actor, peer_id))


@router.get("/{peer_id}/config", response_class=PlainTextResponse)
async def client_config(peer_id: int, principal: Writer, ctx: Ctx, allowed_ips: str | None = Query(default=None, max_length=2000)) -> PlainTextResponse:
    """Contains the peer's private key and PSK: operator role or `peers:write` scope required."""
    text, row = await service.client_config(ctx, peer_id, _override(allowed_ips), actor=principal.actor, fmt="conf")
    return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="{_filename(row["name"])}"'})


@router.get("/{peer_id}/qr")
async def client_qr(peer_id: int, principal: Writer, ctx: Ctx, allowed_ips: str | None = Query(default=None, max_length=2000)) -> Response:
    text, _row = await service.client_config(ctx, peer_id, _override(allowed_ips), actor=principal.actor, fmt="qr")
    return Response(content=service.qr_png(text), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/{peer_id}/share", response_model=ShareCreated)
async def share_peer(peer_id: int, body: ShareCreate, principal: Writer, ctx: Ctx) -> ShareCreated:
    return ShareCreated(**await share_service.create_link(ctx, principal.actor, peer_id, body.expires_in_hours, body.max_uses))


@router.get("/{peer_id}/stats", response_model=StatsSeries)
async def peer_stats(peer_id: int, _: Reader, ctx: Ctx, range: StatsRange = "24h") -> StatsSeries:  # noqa: A002
    return StatsSeries(**await stats_service.series(ctx, range, peer_id=peer_id))
