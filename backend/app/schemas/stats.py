"""Stats schemas."""

from __future__ import annotations

from typing import Literal

from app.schemas.audit import AuditEntry
from app.schemas.common import ApiModel

StatsRange = Literal["1h", "6h", "24h", "7d", "30d"]


class StatsPoint(ApiModel):
    ts: str
    rx: int
    tx: int
    online: int


class StatsSeries(ApiModel):
    range: StatsRange
    bucket_seconds: int
    points: list[StatsPoint]
    rx_total: int
    tx_total: int


class OverviewPoint(ApiModel):
    ts: str
    rx: int
    tx: int


class TopPeer(ApiModel):
    peer_id: int
    name: str
    interface_name: str
    rx: int
    tx: int


class Overview(ApiModel):
    interfaces_total: int
    interfaces_active: int
    peers_total: int
    peers_online: int
    peers_disabled: int
    peers_expiring_7d: int
    rx_total: int
    tx_total: int
    series: list[OverviewPoint]
    top_peers: list[TopPeer]
    recent_activity: list[AuditEntry]
