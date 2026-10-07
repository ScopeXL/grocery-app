"""Kroger product data for the household's store, kept only as long as the headers allow.

(docs/PLAN.md §7.4, ADR 0016)

* **Search results** live in memory for min(60 s, what the headers permit), keyed by the
  normalized term, store and page size. Identical searches in flight share one call. They are
  never written to the database and the term is never logged.
* **Products the household uses** (linked to items) are kept in `kroger_product_cache` until
  their headers' expiry, plus a 60 s memory copy so the amount picker's previews are cheap.

Never call these while holding a write transaction: they write the cache and the usage
counters themselves, and the write lock isn't re-entrant.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select

from dinnerbell.core.clock import Clock
from dinnerbell.db.engine import Database
from dinnerbell.kroger.cachepolicy import CachePolicy
from dinnerbell.kroger.client import KrogerApi
from dinnerbell.kroger.models import KrogerProductCache
from dinnerbell.kroger.parse import Product, product_from_json, product_to_json

MEMORY_TTL = timedelta(seconds=60)
LOOKUP_CONCURRENCY = 4
BATCH_SIZE = 50
# `filter.productId` batches come back with store prices and aisles: `just smoke-kroger`
# verified it on 2026-10-06 (docs/KROGER.md). Set False to fetch products one by one.
BATCH_INCLUDES_PRICES = True

type SearchKey = tuple[str, str, int]


@dataclass(frozen=True, slots=True)
class _Held[T]:
    value: T
    until: datetime


class ProductCatalog:
    def __init__(self, kroger: KrogerApi, db: Database, clock: Clock) -> None:
        self._kroger = kroger
        self._db = db
        self._clock = clock
        self._searches: dict[SearchKey, _Held[tuple[Product, ...]]] = {}
        self._in_flight: dict[SearchKey, asyncio.Task[tuple[Product, ...]]] = {}
        self._products: dict[tuple[str, str], _Held[Product]] = {}

    @property
    def kroger(self) -> KrogerApi:
        return self._kroger

    # ---- search -----------------------------------------------------------------------------

    async def search(self, term: str, location_id: str, *, limit: int = 20) -> tuple[Product, ...]:
        key = (" ".join(term.casefold().split()), location_id, limit)
        held = self._searches.get(key)
        if held is not None and self._clock.now() < held.until:
            return held.value
        task = self._in_flight.get(key)
        if task is None:
            # Its own task: one caller giving up mustn't cancel the search for the others.
            task = asyncio.create_task(self._search_now(key))
            self._in_flight[key] = task
            task.add_done_callback(lambda done: self._finished(key, done))
        return await asyncio.shield(task)

    async def _search_now(self, key: SearchKey) -> tuple[Product, ...]:
        term, location_id, limit = key
        fetched = await self._kroger.search_products(term, location_id, limit=limit)
        until = self._memory_until(fetched.cache)
        if until is not None:
            self._searches[key] = _Held(fetched.data, until)
            for product in fetched.data:
                self._products[(product.product_id, location_id)] = _Held(product, until)
        return fetched.data

    def _finished(self, key: SearchKey, task: asyncio.Task[tuple[Product, ...]]) -> None:
        self._in_flight.pop(key, None)
        if not task.cancelled():
            task.exception()  # retrieved here, so a failure nobody awaited isn't logged

    # ---- products by ID ---------------------------------------------------------------------

    async def product(self, product_id: str, location_id: str) -> Product | None:
        return (await self.products([product_id], location_id)).get(product_id)

    async def products(self, product_ids: Iterable[str], location_id: str) -> dict[str, Product]:
        """The products that Kroger knows at this store, by ID; unknown IDs are left out."""
        wanted = list(dict.fromkeys(product_ids))
        now = self._clock.now()
        found: dict[str, Product] = {}
        for product_id in wanted:
            held = self._products.get((product_id, location_id))
            if held is not None and now < held.until:
                found[product_id] = held.value
        missing = [p for p in wanted if p not in found]
        if missing:
            found.update(await self._from_cache(missing, location_id, now))
        missing = [p for p in wanted if p not in found]
        if missing:
            found.update(await self._fetch(missing, location_id))
        return found

    async def _from_cache(
        self, product_ids: Sequence[str], location_id: str, now: datetime
    ) -> dict[str, Product]:
        async with self._db.read() as session:
            rows = await session.scalars(
                select(KrogerProductCache).where(
                    KrogerProductCache.location_id == location_id,
                    KrogerProductCache.product_id.in_(product_ids),
                    KrogerProductCache.expires_at > now,
                )
            )
            return {row.product_id: product_from_json(row.payload) for row in rows}

    async def _fetch(self, product_ids: Sequence[str], location_id: str) -> dict[str, Product]:
        results: list[tuple[Product, CachePolicy]] = []
        if BATCH_INCLUDES_PRICES:
            for start in range(0, len(product_ids), BATCH_SIZE):
                chunk = product_ids[start : start + BATCH_SIZE]
                fetched = await self._kroger.get_products(chunk, location_id)
                results.extend((product, fetched.cache) for product in fetched.data)
        else:
            gate = asyncio.Semaphore(LOOKUP_CONCURRENCY)

            async def one(product_id: str) -> None:
                async with gate:
                    fetched = await self._kroger.get_product(product_id, location_id)
                if fetched.data is not None:
                    results.append((fetched.data, fetched.cache))

            async with asyncio.TaskGroup() as group:
                for product_id in product_ids:
                    group.create_task(one(product_id))
        await self._keep(results, location_id)
        return {product.product_id: product for product, _ in results}

    async def _keep(self, results: Sequence[tuple[Product, CachePolicy]], location_id: str) -> None:
        now = self._clock.now()
        storable = [(p, policy) for p, policy in results if policy.expires_at is not None]
        for product, policy in results:
            until = self._memory_until(policy)
            if until is not None:
                self._products[(product.product_id, location_id)] = _Held(product, until)
        if not storable:
            return
        async with self._db.write() as tx:
            for product, policy in storable:
                assert policy.expires_at is not None
                await tx.session.merge(
                    KrogerProductCache(
                        product_id=product.product_id,
                        location_id=location_id,
                        payload=product_to_json(product),
                        fetched_at=now,
                        expires_at=policy.expires_at,
                        cache_control_raw=policy.raw[:200],
                    )
                )

    # ---- housekeeping -----------------------------------------------------------------------

    async def purge_expired(self) -> int:
        """Delete cache rows past their expiry (an hourly job) and drop stale memory."""
        now = self._clock.now()
        self._searches = {k: v for k, v in self._searches.items() if now < v.until}
        self._products = {k: v for k, v in self._products.items() if now < v.until}
        async with self._db.write() as tx:
            result = await tx.session.execute(
                delete(KrogerProductCache).where(KrogerProductCache.expires_at <= now)
            )
            return cast(CursorResult[Any], result).rowcount

    def forget(self) -> None:
        self._searches.clear()
        self._products.clear()

    def _memory_until(self, policy: CachePolicy) -> datetime | None:
        if policy.expires_at is None:
            return None
        return min(policy.expires_at, self._clock.now() + MEMORY_TTL)
