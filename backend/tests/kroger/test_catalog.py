"""Kroger data kept only as long as the headers allow (docs/PLAN.md §7.4, ADR 0016)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from dinnerbell.core.clock import FakeClock
from dinnerbell.db.engine import Database, make_database
from dinnerbell.kroger.cachepolicy import CachePolicy
from dinnerbell.kroger.catalog import MEMORY_TTL, ProductCatalog
from dinnerbell.kroger.client import Fetched
from dinnerbell.kroger.fake import FakeKroger
from dinnerbell.kroger.models import KrogerProductCache
from dinnerbell.kroger.parse import Product

STORE = "99999001"


class CountingKroger(FakeKroger):
    """The fake, counting calls, with a cache lifetime the test controls."""

    def __init__(self, clock: FakeClock) -> None:
        super().__init__(clock)
        self.clock = clock
        self.searches = 0
        self.lookups = 0
        self.lifetime: timedelta | None = timedelta(hours=1)
        self.pause = asyncio.Event()
        self.pause.set()

    def _policy(self) -> CachePolicy:
        if self.lifetime is None:
            return CachePolicy(None, "cache-control: no-store")
        return CachePolicy(self.clock.now() + self.lifetime, "test")

    async def search_products(
        self, term: str, location_id: str, *, limit: int = 20, start: int = 1
    ) -> Fetched[tuple[Product, ...]]:
        self.searches += 1
        await self.pause.wait()
        return await super().search_products(term, location_id, limit=limit, start=start)

    async def get_product(self, product_id: str, location_id: str) -> Fetched[Product | None]:
        self.lookups += 1
        return await super().get_product(product_id, location_id)

    async def get_products(
        self, product_ids: Sequence[str], location_id: str
    ) -> Fetched[tuple[Product, ...]]:
        self.lookups += 1  # one call to Kroger, however many IDs
        return await super().get_products(product_ids, location_id)


@pytest.fixture(params=[True, False], ids=["batched", "one-by-one"])
def batched(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> bool:
    """Run each test with Kroger batches (what M1 verified) and with per-ID lookups."""
    value: bool = request.param
    monkeypatch.setattr("dinnerbell.kroger.catalog.BATCH_INCLUDES_PRICES", value)
    return value


@pytest.fixture
async def db(data_dir: Path) -> AsyncIterator[Database]:
    database = make_database(data_dir / "dinnerbell.db")
    yield database
    await database.dispose()


@pytest.fixture
def kroger(clock: FakeClock) -> CountingKroger:
    return CountingKroger(clock)


@pytest.fixture
def catalog(kroger: CountingKroger, db: Database, clock: FakeClock) -> ProductCatalog:
    return ProductCatalog(kroger, db, clock)


async def cached_rows(db: Database) -> int:
    async with db.read() as session:
        return await session.scalar(select(func.count()).select_from(KrogerProductCache)) or 0


async def test_identical_searches_share_one_call_and_a_minute_of_memory(
    catalog: ProductCatalog, kroger: CountingKroger, clock: FakeClock, db: Database
) -> None:
    kroger.pause.clear()
    first = asyncio.create_task(catalog.search("Cheese", STORE))
    second = asyncio.create_task(catalog.search("  cheese ", STORE))
    await asyncio.sleep(0)
    kroger.pause.set()
    assert (await first) == (await second)
    assert kroger.searches == 1
    await catalog.search("CHEESE", STORE)
    assert kroger.searches == 1
    clock.advance(seconds=MEMORY_TTL.total_seconds())
    await catalog.search("cheese", STORE)
    assert kroger.searches == 2
    assert await cached_rows(db) == 0  # search results are never written down


async def test_a_caller_giving_up_doesnt_cancel_the_shared_search(
    catalog: ProductCatalog, kroger: CountingKroger
) -> None:
    kroger.pause.clear()
    quitter = asyncio.create_task(catalog.search("milk", STORE))
    stayer = asyncio.create_task(catalog.search("milk", STORE))
    await asyncio.sleep(0)
    quitter.cancel()
    kroger.pause.set()
    assert [p.description for p in await stayer] == ["Sample Whole Milk"]


async def test_no_store_means_nothing_is_kept_anywhere(
    catalog: ProductCatalog, kroger: CountingKroger, db: Database, batched: bool
) -> None:
    kroger.lifetime = None
    await catalog.search("milk", STORE)
    await catalog.search("milk", STORE)
    assert kroger.searches == 2
    await catalog.products(["0000000000001"], STORE)
    await catalog.products(["0000000000001"], STORE)
    assert kroger.lookups == 2
    assert await cached_rows(db) == 0


async def test_linked_products_are_cached_until_their_headers_expire(
    catalog: ProductCatalog,
    kroger: CountingKroger,
    clock: FakeClock,
    db: Database,
    batched: bool,
) -> None:
    found = await catalog.products(["0000000000001", "0000000000005", "0000000009999"], STORE)
    assert sorted(found) == ["0000000000001", "0000000000005"]
    first = 1 if batched else 3  # one batch call, or one call per ID
    assert kroger.lookups == first
    assert await cached_rows(db) == 2
    clock.advance(minutes=5)  # memory is gone, the database copy is still fresh
    again = await catalog.products(["0000000000001"], STORE)
    assert again["0000000000001"] == found["0000000000001"]
    assert kroger.lookups == first
    clock.advance(hours=1)
    assert await catalog.purge_expired() == 2
    assert await cached_rows(db) == 0
    await catalog.products(["0000000000001"], STORE)
    assert kroger.lookups == first + 1


async def test_a_cached_product_comes_back_identical(
    catalog: ProductCatalog, clock: FakeClock, batched: bool
) -> None:
    ids: Sequence[str] = ("0000000000001", "0000000000004", "0000000000008", "0000000000019")
    fresh = await catalog.products(ids, STORE)
    clock.advance(minutes=5)
    assert await catalog.products(ids, STORE) == fresh  # read back from kroger_product_cache
