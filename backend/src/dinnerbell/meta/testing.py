"""Test-only endpoints, mounted only when DINNERBELL_TEST_MODE=1 on localhost (end-to-end runs)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import delete, update

from dinnerbell.auth.models import Device
from dinnerbell.catalog.models import Item
from dinnerbell.household.models import AppMeta, Household, Member
from dinnerbell.kroger.models import KrogerApiUsage, KrogerProductCache
from dinnerbell.meals.models import Dish, DishItem, Photo
from dinnerbell.state import StateDep
from dinnerbell.stores.models import Store, StoreSection

router = APIRouter(prefix="/api/_test", include_in_schema=False)


@router.post("/reset", status_code=204)
async def reset(state: StateDep) -> None:
    async with state.db.write() as tx:
        for model in (
            DishItem,
            Dish,
            Photo,
            Item,
            StoreSection,
            Store,
            KrogerProductCache,
            KrogerApiUsage,
        ):
            await tx.session.execute(delete(model))
        await tx.session.execute(delete(Device))
        await tx.session.execute(delete(Member))
        await tx.session.execute(
            update(Household).values(name="Our household", active_store_id=None)
        )
        await tx.session.execute(update(AppMeta).values(auth_epoch=AppMeta.auth_epoch + 1))
        meta = await tx.session.get(AppMeta, 1)
        epoch = meta.auth_epoch if meta else state.auth.epoch + 1
    state.auth.epoch = epoch
    state.auth.known_devices.clear()
    state.auth.revoked_devices.clear()
    state.auth.last_seen_written.clear()
    state.limiter.reset()
    state.catalog.forget()
    state.hub.drop_all()


@router.post("/drop-streams", status_code=204)
async def drop_streams(state: StateDep) -> None:
    state.hub.drop_all()


@router.post("/revoke-sessions", status_code=204)
async def revoke_sessions(state: StateDep) -> None:
    async with state.db.write() as tx:
        await tx.session.execute(update(AppMeta).values(auth_epoch=AppMeta.auth_epoch + 1))
        meta = await tx.session.get(AppMeta, 1)
        epoch = meta.auth_epoch if meta else state.auth.epoch + 1
    state.auth.epoch = epoch
