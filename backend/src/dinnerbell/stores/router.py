"""Find a store near a ZIP code and make it the household's store."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from dinnerbell.auth.deps import SessionDep
from dinnerbell.catalog.service import require_store
from dinnerbell.shopping import service as shopping
from dinnerbell.state import StateDep
from dinnerbell.stores import service
from dinnerbell.stores.models import Store, StoreSection
from dinnerbell.stores.schemas import (
    ActiveStoreOut,
    ChooseStore,
    SectionOrderIn,
    SectionOut,
    StoreOption,
    StoreOut,
    ZipCode,
)

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("/search")
async def search_stores(
    zip_code: Annotated[ZipCode, Query(alias="zip")], state: StateDep, session: SessionDep
) -> list[StoreOption]:
    return await service.search(state.catalog.kroger, zip_code)


@router.get("/active")
async def get_active_store(state: StateDep, session: SessionDep) -> ActiveStoreOut:
    async with state.db.read() as db:
        store = await service.active_store(db)
        return ActiveStoreOut(store=service.store_out(store) if store else None)


@router.put("/active")
async def choose_store(body: ChooseStore, state: StateDep, session: SessionDep) -> StoreOut:
    location, domain = await service.fetch_location(state.catalog.kroger, body.location_id)
    async with state.db.write() as tx:
        store = await service.choose(tx.session, location, domain)
        tx.publish("settings.changed")
        return service.store_out(store)


@router.get("/active/sections")
async def get_sections(state: StateDep, session: SessionDep) -> list[SectionOut]:
    """The store's walking order (UX §4.16)."""
    store = await require_store(state)
    async with state.db.read() as db:
        return _sections_out(await service.sections(db, store))


@router.put("/active/sections")
async def put_sections(
    body: SectionOrderIn, state: StateDep, session: SessionDep
) -> list[SectionOut]:
    """Save a new walking order. Lists being shopped re-sort to match, on every phone."""
    found = await require_store(state)
    async with state.db.write() as tx:
        store = await tx.session.get(Store, found.id)
        assert store is not None
        orders = await service.reorder(tx.session, store, body.ids)
        for trip, changed in await shopping.resort(tx.session, store.id, orders):
            out = await shopping.trip_out(tx.session, trip)
            tx.publish("trip.items", shopping.trip_event(out, None, changed))
        tx.publish("plan.changed")
        return _sections_out(await service.sections(tx.session, store))


def _sections_out(found: list[StoreSection]) -> list[SectionOut]:
    return [SectionOut(id=s.id, key=s.key, label=s.label) for s in found]
