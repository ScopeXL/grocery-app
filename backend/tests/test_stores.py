"""Finding and choosing the household's store (docs/PLAN.md §7.3). Fake Kroger only."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from dinnerbell.kroger.client import KrogerDailyLimitError
from dinnerbell.kroger.errors import about_time
from dinnerbell.state import AppState
from dinnerbell.stores.models import StoreSection
from tests.support import CSRF, StreamProbe, login


async def test_search_lists_nearby_stores_without_fuel_centers(client: httpx.AsyncClient) -> None:
    await login(client)
    response = await client.get("/api/stores/search", params={"zip": "00001"})
    assert response.status_code == 200
    stores = response.json()
    assert [store["name"] for store in stores] == [
        "Sample Market Downtown",
        "Sample Market Northside",
    ]
    assert stores[1]["address_lines"] == ["200 Example Avenue", "Unit 2", "Sampleton, ST 00002"]
    assert (await client.get("/api/stores/search", params={"zip": "00000"})).json() == []


async def test_a_zip_must_be_five_digits(client: httpx.AsyncClient) -> None:
    await login(client)
    response = await client.get("/api/stores/search", params={"zip": "123"})
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == ["zip"]


async def test_store_search_needs_a_sign_in(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/stores/search", params={"zip": "00001"})
    assert response.status_code == 401


async def test_choosing_a_store_saves_it_and_seeds_the_walk(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    await login(client)
    assert (await client.get("/api/stores/active")).json() == {"store": None}
    stream = StreamProbe(app, cookie=f"dinnerbell={client.cookies['dinnerbell']}").start()
    try:
        await stream.wait_started()
        response = await client.put(
            "/api/stores/active", json={"location_id": "99999001"}, headers=CSRF
        )
        assert response.status_code == 200
        await stream.wait_for(lambda frames: any(f["type"] == "settings.changed" for f in frames))
    finally:
        await stream.close()
    store = {
        "name": "Sample Market Downtown",
        "address_lines": ["100 Sample Street", "Sampleton, ST 00001"],
    }
    assert response.json() == store
    assert (await client.get("/api/stores/active")).json() == {"store": store}

    state: AppState = app.state.dinnerbell
    async with state.db.read() as db:
        sections = list(await db.scalars(select(StoreSection).order_by(StoreSection.sort_index)))
    assert [s.key for s in sections][:3] == ["cat:produce", "cat:bakery", "cat:deli"]
    assert sections[-1].key == "cat:other"

    # Switching stores and back never duplicates a store's sections.
    await client.put("/api/stores/active", json={"location_id": "99999002"}, headers=CSRF)
    await client.put("/api/stores/active", json={"location_id": "99999001"}, headers=CSRF)
    async with state.db.read() as db:
        pairs = list((await db.execute(select(StoreSection.store_id, StoreSection.key))).all())
    assert len(pairs) == 2 * len(sections)  # each of the two stores has its own set, once


async def test_fuel_centers_and_unknown_stores_cant_be_chosen(client: httpx.AsyncClient) -> None:
    await login(client)
    for location_id in ("99999901", "12345678"):
        response = await client.put(
            "/api/stores/active", json={"location_id": location_id}, headers=CSRF
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "store_not_found"


async def test_the_daily_limit_reads_as_a_quiet_plain_message(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    state: AppState = app.state.dinnerbell
    retry_at = datetime(2026, 10, 6, 19, 40, tzinfo=UTC)

    async def limited(zip_code: str, *, limit: int = 20) -> object:
        raise KrogerDailyLimitError(retry_at)

    state.catalog.kroger.locations = limited  # type: ignore[method-assign]
    await login(client)
    response = await client.get("/api/stores/search", params={"zip": "00001"})
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "kroger_daily_limit"
    assert error["message"] == (
        "Store search is paused until about 3:40 PM — your list still works."
    )
    assert error["retry_at"] == retry_at.isoformat()


def test_retry_times_read_naturally() -> None:
    zone = ZoneInfo("America/New_York")
    now = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)  # 10:00 AM in New York
    assert about_time(datetime(2026, 10, 6, 16, 5, tzinfo=UTC), zone, now) == "12:05 PM"
    assert about_time(datetime(2026, 10, 7, 4, 30, tzinfo=UTC), zone, now) == "12:30 AM tomorrow"
    assert about_time(datetime(2026, 10, 9, 13, 0, tzinfo=UTC), zone, now) == "Friday 9:00 AM"
