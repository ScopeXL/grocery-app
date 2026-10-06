"""Find a store near a ZIP code and make it the household's store."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from dinnerbell.auth.deps import SessionDep
from dinnerbell.state import StateDep
from dinnerbell.stores import service
from dinnerbell.stores.schemas import ActiveStoreOut, ChooseStore, StoreOption, StoreOut, ZipCode

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
