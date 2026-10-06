"""Kroger's daily limits (docs/PLAN.md §7.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dinnerbell.core.clock import FakeClock
from dinnerbell.kroger.client import KrogerDailyLimitError
from dinnerbell.kroger.usage import Bucket, MemoryUsageStore, UsageGuard

START = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(START)


@pytest.fixture
def store() -> MemoryUsageStore:
    return MemoryUsageStore()


@pytest.fixture
def guard(store: MemoryUsageStore, clock: FakeClock) -> UsageGuard:
    return UsageGuard(store, clock)


async def test_calls_are_counted_per_bucket_and_window(
    guard: UsageGuard, store: MemoryUsageStore, clock: FakeClock
) -> None:
    for _ in range(3):
        assert await guard.record(Bucket.PRODUCTS, 200) is None
    await guard.record(Bucket.LOCATIONS, 200)
    assert (await store.load(Bucket.PRODUCTS)).calls == 3
    assert (await store.load(Bucket.LOCATIONS)).calls == 1
    clock.advance(hours=24)
    await guard.record(Bucket.PRODUCTS, 200)
    usage = await store.load(Bucket.PRODUCTS)
    assert (usage.calls, usage.window_started_at) == (1, clock.now())


async def test_a_429_in_a_window_we_saw_start_blocks_until_it_ends(
    guard: UsageGuard, clock: FakeClock
) -> None:
    await guard.record(Bucket.PRODUCTS, 200)
    clock.advance(hours=5)
    assert await guard.record(Bucket.PRODUCTS, 429) == START + timedelta(hours=24)
    with pytest.raises(KrogerDailyLimitError) as blocked:
        await guard.check(Bucket.PRODUCTS)
    assert blocked.value.retry_at == START + timedelta(hours=24)
    await guard.check(Bucket.LOCATIONS)  # other buckets keep working
    clock.set(START + timedelta(hours=24))
    await guard.check(Bucket.PRODUCTS)


async def test_an_unknown_window_probes_hourly_then_doubles_up_to_six_hours(
    guard: UsageGuard, store: MemoryUsageStore, clock: FakeClock
) -> None:
    waits: list[timedelta] = []
    for _ in range(5):
        until = await guard.record(Bucket.PRODUCTS, 429)
        assert until is not None
        waits.append(until - clock.now())
        clock.set(until)
    assert waits == [timedelta(hours=h) for h in (1, 2, 4, 6, 6)]
    assert await guard.record(Bucket.PRODUCTS, 200) is None
    usage = await store.load(Bucket.PRODUCTS)
    assert (usage.blocked_until, usage.probe_backoff, usage.calls) == (None, None, 1)
    assert usage.window_started_at == clock.now()  # the first call after a block starts a window


async def test_a_429_after_the_window_ended_is_treated_as_unknown(
    guard: UsageGuard, clock: FakeClock
) -> None:
    await guard.record(Bucket.PRODUCTS, 200)
    clock.advance(hours=25)
    until = await guard.record(Bucket.PRODUCTS, 429)
    assert until == clock.now() + timedelta(hours=1)
