"""Traffic sampling, bucketed series, dashboard overview and retention."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.context import AppContext
from app.core.errors import NotFound
from app.core.security import iso, utcnow
from app.db.connection import connect
from app.db.repos import audit as audit_repo
from app.db.repos import interfaces as interfaces_repo
from app.db.repos import peers as peers_repo
from app.db.repos import sessions as sessions_repo
from app.db.repos import settings as settings_repo
from app.db.repos import share_links as share_repo
from app.db.repos import stats as repo

logger = logging.getLogger(__name__)

ONLINE_WINDOW = timedelta(seconds=180)
CONTINUITY_SECONDS = 300
RANGES: dict[str, tuple[int, int]] = {  # range -> (window seconds, bucket seconds)
    "1h": (3600, 60),
    "6h": (6 * 3600, 300),
    "24h": (24 * 3600, 900),
    "7d": (7 * 86400, 3600),
    "30d": (30 * 86400, 4 * 3600),
}


# --- sampler ---------------------------------------------------------------------


async def sample(ctx: AppContext) -> int:
    """Poll each enabled+active interface and record per-peer deltas. Returns rows written."""
    written = 0
    async with connect(ctx.db_path) as db:
        for iface in await interfaces_repo.list_all(db):
            if not iface["enabled"] or not await ctx.backend.is_active(iface["name"]):
                continue
            try:
                dump = await ctx.backend.dump(iface["name"])
            except Exception:  # noqa: BLE001 - keep sampling the other interfaces
                logger.exception("Stats dump failed for %s", iface["name"])
                continue
            live = {p.public_key: p for p in dump.peers}
            for peer in await peers_repo.list_for_interface(db, iface["id"]):
                entry = live.get(peer["public_key"])
                if entry is None:
                    continue
                written += await _record_peer(ctx, db, peer, entry)
    return written


async def _record_peer(ctx: AppContext, db: Any, peer: dict[str, Any], entry: Any) -> int:
    now = utcnow()
    peer_id = peer["id"]
    prev_rx, prev_tx = ctx.live.raw_counters.get(peer_id, (peer["rx_total"], peer["tx_total"]))
    rx_delta = entry.rx - prev_rx if entry.rx >= prev_rx else entry.rx
    tx_delta = entry.tx - prev_tx if entry.tx >= prev_tx else entry.tx
    ctx.live.raw_counters[peer_id] = (entry.rx, entry.tx)
    ctx.live.endpoints[peer_id] = entry.endpoint
    online = entry.latest_handshake is not None and (now - entry.latest_handshake) <= ONLINE_WINDOW
    fields: dict[str, Any] = {}
    if rx_delta or tx_delta:
        fields["rx_total"] = peer["rx_total"] + rx_delta
        fields["tx_total"] = peer["tx_total"] + tx_delta
    handshake = iso(entry.latest_handshake) if entry.latest_handshake else None
    if handshake and handshake != peer["last_handshake_at"]:
        fields["last_handshake_at"] = handshake
    if fields:
        await peers_repo.update(db, peer_id, None, **fields)
    state_changed = ctx.live.last_online.get(peer_id) != online
    stale = time.monotonic() - ctx.live.last_sample_ts.get(peer_id, -1e9) >= CONTINUITY_SECONDS
    if rx_delta > 0 or tx_delta > 0 or state_changed or stale:
        await repo.insert_sample(db, peer_id, iso(now), rx_delta, tx_delta, online)
        ctx.live.last_sample_ts[peer_id] = time.monotonic()
        ctx.live.last_online[peer_id] = online
        return 1
    return 0


# --- queries ---------------------------------------------------------------------


def _bucket_ts(bucket: int) -> str:
    return iso(datetime.fromtimestamp(int(bucket), tz=timezone.utc))


async def series(ctx: AppContext, range_key: str, *, interface_name: str | None = None, peer_id: int | None = None) -> dict[str, Any]:
    window, bucket = RANGES[range_key]
    since = iso(utcnow() - timedelta(seconds=window))
    async with connect(ctx.db_path) as db:
        interface_id = None
        if interface_name is not None:
            iface = await interfaces_repo.get_by_name(db, interface_name)
            if iface is None:
                raise NotFound("Interface not found")
            interface_id = iface["id"]
            totals = await interfaces_repo.peer_summary(db, interface_id, iso(utcnow() - ONLINE_WINDOW))
            rx_total, tx_total = totals["rx_total"], totals["tx_total"]
        else:
            assert peer_id is not None
            peer = await peers_repo.get(db, peer_id)
            if peer is None:
                raise NotFound("Peer not found")
            rx_total, tx_total = peer["rx_total"], peer["tx_total"]
        rows = await repo.bucketed(db, since=since, bucket_seconds=bucket, interface_id=interface_id, peer_id=peer_id)
    return {
        "range": range_key,
        "bucket_seconds": bucket,
        "points": [{"ts": _bucket_ts(r["bucket"]), "rx": int(r["rx"]), "tx": int(r["tx"]), "online": int(r["online"])} for r in rows],
        "rx_total": int(rx_total),
        "tx_total": int(tx_total),
    }


async def overview(ctx: AppContext, range_key: str) -> dict[str, Any]:
    window, bucket = RANGES[range_key]
    now = utcnow()
    since = iso(now - timedelta(seconds=window))
    async with connect(ctx.db_path) as db:
        interfaces = await interfaces_repo.list_all(db)
        active = 0
        for iface in interfaces:
            if await ctx.backend.is_active(iface["name"]):
                active += 1
        counts = await peers_repo.overview_counts(db, iso(now), iso(now - ONLINE_WINDOW), iso(now + timedelta(days=7)))
        rows = await repo.bucketed(db, since=since, bucket_seconds=bucket)
        top = await repo.top_peers(db, since, limit=5)
        recent = await audit_repo.recent(db, 10)
    return {
        "interfaces_total": len(interfaces),
        "interfaces_active": active,
        "peers_total": counts["total"],
        "peers_online": counts["online"],
        "peers_disabled": counts["disabled"],
        "peers_expiring_7d": counts["expiring"],
        "rx_total": counts["rx_total"],
        "tx_total": counts["tx_total"],
        "series": [{"ts": _bucket_ts(r["bucket"]), "rx": int(r["rx"]), "tx": int(r["tx"])} for r in rows],
        "top_peers": [{"peer_id": r["peer_id"], "name": r["name"], "interface_name": r["interface_name"], "rx": int(r["rx"]), "tx": int(r["tx"])} for r in top],
        "recent_activity": recent,
    }


# --- retention -------------------------------------------------------------------


async def retention(ctx: AppContext) -> dict[str, int]:
    now = utcnow()
    async with connect(ctx.db_path) as db:
        values = await settings_repo.get_all(db)
        audit_days = int(values["audit_retention_days"] or 90)
        stats_days = int(values["stats_retention_days"] or ctx.settings.stats_retention_days)
        removed = {
            "audit": await audit_repo.delete_before(db, iso(now - timedelta(days=audit_days))),
            "stats": await repo.delete_before(db, iso(now - timedelta(days=stats_days))),
            "sessions": await sessions_repo.delete_expired(db, iso(now - timedelta(days=1))),
            "share_links": await share_repo.delete_expired(db, iso(now)),
        }
    if any(removed.values()):
        logger.info("Retention removed %s", removed)
    return removed


def parse_range(value: str | None, default: str = "24h") -> str:
    return value if value in RANGES else default
