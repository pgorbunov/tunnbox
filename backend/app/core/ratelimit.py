"""Bounded in-memory sliding-window rate limiter keyed by (bucket, key)."""

from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    """Sliding window limiter.

    `check(bucket, key, limit, window)` records a hit and returns
    `(allowed, retry_after_seconds)`. Memory is bounded by `max_keys`: the
    least recently touched keys are evicted first.
    """

    def __init__(self, max_keys: int = 10_000) -> None:
        self.max_keys = max_keys
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def check(self, bucket: str, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        composite = (bucket, key)
        hits = self._hits.pop(composite, None)
        if hits is None:
            hits = deque()
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = int(hits[0] + window_seconds - now) + 1
            self._hits[composite] = hits
            return False, retry_after
        hits.append(now)
        self._hits[composite] = hits
        self._evict()
        return True, 0

    def reset(self, bucket: str, key: str) -> None:
        self._hits.pop((bucket, key), None)

    def _evict(self) -> None:
        while len(self._hits) > self.max_keys:
            oldest = next(iter(self._hits))
            del self._hits[oldest]
