"""Tiny asyncio job scheduler with per-job intervals and error isolation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

JobFn = Callable[[], Awaitable[None]]


@dataclass
class Job:
    name: str
    fn: JobFn
    interval: float
    run_immediately: bool = True


class Scheduler:
    """Runs registered coroutines periodically until `stop()` is awaited."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._stop = asyncio.Event()

    def add_job(self, name: str, fn: JobFn, interval: float, run_immediately: bool = True) -> None:
        self._jobs[name] = Job(name=name, fn=fn, interval=interval, run_immediately=run_immediately)

    async def run_once(self, name: str) -> None:
        """Execute one job now (used by tests and reconcile-at-startup)."""
        await self._jobs[name].fn()

    def start(self) -> None:
        self._stop = asyncio.Event()
        self._tasks = [asyncio.create_task(self._loop(job), name=f"job:{job.name}") for job in self._jobs.values()]

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutdown must not raise
                pass
        self._tasks = []

    async def _loop(self, job: Job) -> None:
        if not job.run_immediately:
            await self._sleep(job.interval)
        while not self._stop.is_set():
            try:
                await job.fn()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - one failing job must not kill the others
                logger.exception("Background job %s failed", job.name)
            await self._sleep(job.interval)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
