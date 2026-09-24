"""/api/interfaces — interface CRUD, up/down, server config, stats, peers listing."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import PlainTextResponse

from app.api.deps import Ctx, require
from app.schemas.interfaces import Interface, InterfaceCreate, InterfaceUpdate
from app.schemas.peers import NextIp, Peer, PeerCreate
from app.schemas.stats import StatsRange, StatsSeries
from app.services import interfaces as service
from app.services import peers as peers_service
from app.services import stats as stats_service
from app.services.auth import Principal

router = APIRouter(prefix="/interfaces", tags=["interfaces"])
Reader = Annotated[Principal, Depends(require("viewer", "read"))]
Writer = Annotated[Principal, Depends(require("operator", "interfaces:write"))]
PeerWriter = Annotated[Principal, Depends(require("operator", "peers:write"))]
Admin = Annotated[Principal, Depends(require("admin", "admin"))]


@router.get("", response_model=list[Interface])
async def list_interfaces(_: Reader, ctx: Ctx) -> list[Interface]:
    return [Interface(**i) for i in await service.list_interfaces(ctx)]


@router.post("", response_model=Interface, status_code=status.HTTP_201_CREATED)
async def create_interface(body: InterfaceCreate, principal: Writer, ctx: Ctx) -> Interface:
    return Interface(**await service.create_interface(ctx, principal.actor, body, is_admin=principal.role == "admin"))


@router.get("/{name}", response_model=Interface)
async def get_interface(name: str, _: Reader, ctx: Ctx) -> Interface:
    return Interface(**await service.get_interface(ctx, name))


@router.patch("/{name}", response_model=Interface)
async def update_interface(name: str, body: InterfaceUpdate, principal: Writer, ctx: Ctx) -> Interface:
    return Interface(**await service.update_interface(ctx, principal.actor, name, body, is_admin=principal.role == "admin"))


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interface(name: str, principal: Writer, ctx: Ctx) -> Response:
    await service.delete_interface(ctx, principal.actor, name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{name}/up", response_model=Interface)
async def interface_up(name: str, principal: Writer, ctx: Ctx) -> Interface:
    return Interface(**await service.set_interface_state(ctx, principal.actor, name, True))


@router.post("/{name}/down", response_model=Interface)
async def interface_down(name: str, principal: Writer, ctx: Ctx) -> Interface:
    return Interface(**await service.set_interface_state(ctx, principal.actor, name, False))


@router.get("/{name}/config", response_class=PlainTextResponse)
async def server_config(name: str, _: Admin, ctx: Ctx) -> PlainTextResponse:
    text = await service.server_config_text(ctx, name)
    return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="{name}.conf"'})


@router.get("/{name}/stats", response_model=StatsSeries)
async def interface_stats(name: str, _: Reader, ctx: Ctx, range: StatsRange = "24h") -> StatsSeries:  # noqa: A002
    return StatsSeries(**await stats_service.series(ctx, range, interface_name=name))


@router.get("/{name}/peers", response_model=list[Peer])
async def list_peers(
    name: str,
    _: Reader,
    ctx: Ctx,
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, pattern="^(online|offline|disabled|expired)$"),  # noqa: A002
    sort: str = Query(default="name", pattern="^(name|handshake|rx|tx|created)$"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> list[Peer]:
    rows = await peers_service.list_for_interface(ctx, name, q=q, status=status, sort=sort, order=order)
    return [Peer(**p) for p in rows]


@router.post("/{name}/peers", response_model=Peer, status_code=status.HTTP_201_CREATED)
async def create_peer(name: str, body: PeerCreate, principal: PeerWriter, ctx: Ctx) -> Peer:
    return Peer(**await peers_service.create_peer(ctx, principal.actor, name, body, is_admin=principal.role == "admin"))


@router.get("/{name}/next-ip", response_model=NextIp)
async def next_ip(name: str, _: Reader, ctx: Ctx) -> NextIp:
    return NextIp(allowed_ips=await peers_service.next_ip(ctx, name))
