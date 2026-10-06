"""A tiny scheduler for background jobs (one loop per job, one place to stop them all)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from dinnerbell.core.logging import get_logger

log = get_logger(__name__)


class Jobs:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()

    def every(self, name: str, interval_s: float, job: Callable[[], Awaitable[None]]) -> None:
        async def loop() -> None:
            while not self._stopping.is_set():
                try:
                    await job()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("job.failed", job=name)
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=interval_s)
                except TimeoutError:
                    pass

        self._tasks.append(asyncio.create_task(loop(), name=f"job:{name}"))

    async def stop(self, timeout_s: float = 5.0) -> None:
        self._stopping.set()
        if not self._tasks:
            return
        _, pending = await asyncio.wait(self._tasks, timeout=timeout_s)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()
