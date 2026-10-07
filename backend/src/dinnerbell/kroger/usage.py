"""Kroger's daily limits, tracked per API bucket (docs/PLAN.md §7.1 and §7.2).

Limits are per client ID, over a rolling 24 h from the first call. A 429 means the day's limit
is used up, so nothing goes out until `blocked_until`:

* if we saw the current window start, that's the window start + 24 h;
* if we didn't (a fresh database, or the window we counted had already ended), block for 1 h,
  then let one probe through, doubling the wait up to 6 h while the probes keep getting 429s.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from dinnerbell.core.clock import Clock
from dinnerbell.kroger.client import KrogerDailyLimitError


class Bucket(StrEnum):
    PRODUCTS = "products"  # search and by-ID share one bucket
    LOCATIONS = "locations"
    CHAINS = "chains"
    CART = "cart"


# Products: Kroger's docs (its responses carry no rate headers). Locations and chains: the
# `ratelimit-limit` header the smoke test saw (docs/KROGER.md), not the 1,600 the docs state.
DAILY_LIMITS: dict[Bucket, int] = {
    Bucket.PRODUCTS: 10_000,
    Bucket.LOCATIONS: 5_000,
    Bucket.CHAINS: 5_000,
    Bucket.CART: 5_000,
}
WINDOW = timedelta(hours=24)
FIRST_PROBE = timedelta(hours=1)
LONGEST_PROBE = timedelta(hours=6)


@dataclass(frozen=True, slots=True)
class Usage:
    bucket: Bucket
    window_started_at: datetime | None = None
    calls: int = 0
    blocked_until: datetime | None = None
    last_429_at: datetime | None = None
    probe_backoff: timedelta | None = None  # set while blocked with an unknown window start


class UsageStore(Protocol):
    async def load(self, bucket: Bucket) -> Usage: ...

    async def save(self, usage: Usage) -> None: ...


class MemoryUsageStore:
    """For the smoke test and unit tests; the app stores usage in `kroger_api_usage`."""

    def __init__(self) -> None:
        self._rows: dict[Bucket, Usage] = {}

    async def load(self, bucket: Bucket) -> Usage:
        return self._rows.get(bucket, Usage(bucket))

    async def save(self, usage: Usage) -> None:
        self._rows[usage.bucket] = usage


class UsageGuard:
    def __init__(self, store: UsageStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def check(self, bucket: Bucket) -> None:
        """Raise before a call goes out while the bucket is blocked."""
        usage = await self._store.load(bucket)
        if usage.blocked_until is not None and self._clock.now() < usage.blocked_until:
            raise KrogerDailyLimitError(usage.blocked_until)

    async def record(
        self, bucket: Bucket, status: int, *, reset_after: timedelta | None = None
    ) -> datetime | None:
        """Count one call that reached Kroger. Returns `blocked_until` when it was a 429.

        `reset_after` is Kroger's own `ratelimit-reset` countdown, when it sends one; it beats
        any estimate of ours.
        """
        now = self._clock.now()
        usage = await self._store.load(bucket)
        # The first call after a block, or after 24 h, starts Kroger's next window.
        new_window = (
            usage.blocked_until is not None
            or usage.window_started_at is None
            or now - usage.window_started_at >= WINDOW
        )
        if new_window:
            usage = replace(usage, window_started_at=now, calls=0)
        usage = replace(usage, calls=usage.calls + 1)
        if status != 429:
            usage = replace(usage, blocked_until=None, probe_backoff=None)
            await self._store.save(usage)
            return None
        if reset_after is not None and timedelta(0) < reset_after <= WINDOW:
            usage = replace(usage, blocked_until=now + reset_after, probe_backoff=None)
        elif usage.probe_backoff is None and not new_window and usage.window_started_at:
            # We saw this window start, so Kroger resets 24 h after it.
            usage = replace(usage, blocked_until=usage.window_started_at + WINDOW)
        else:
            backoff = (
                min(usage.probe_backoff * 2, LONGEST_PROBE) if usage.probe_backoff else FIRST_PROBE
            )
            usage = replace(usage, blocked_until=now + backoff, probe_backoff=backoff)
        usage = replace(usage, last_429_at=now)
        await self._store.save(usage)
        return usage.blocked_until
