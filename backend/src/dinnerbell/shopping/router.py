"""Saved lists: save the plan's list, shop it from any phone (online or not), and history.

Finishing and reopening are ops like check-offs, so they work offline. Every trip event carries
the change itself (PLAN §9.3), so a phone in the store doesn't need to refetch.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select

from dinnerbell.auth.deps import SessionDep
from dinnerbell.catalog import service as items
from dinnerbell.catalog.models import Item
from dinnerbell.core.errors import AppError
from dinnerbell.kroger.client import KrogerError
from dinnerbell.kroger.parse import Product
from dinnerbell.planning import listview
from dinnerbell.planning.service import member_for
from dinnerbell.shopping import again, ops, service
from dinnerbell.shopping.models import TripItem
from dinnerbell.shopping.schemas import MAX_OPS_BYTES, OpsIn, OpsOut, TripOut, TripsOut
from dinnerbell.state import AppState, StateDep
from dinnerbell.stores.models import StoreSection
from dinnerbell.stores.service import active_store

router = APIRouter(prefix="/api", tags=["shopping"])
log = structlog.get_logger("dinnerbell.shopping")


@router.post("/trips", status_code=201)
async def save_list(state: StateDep, session: SessionDep, response: Response) -> TripOut:
    """Save list (UX §4.11), or bring the saved list up to date with the plan's list."""
    data, live, built = await listview.build(state)
    described = listview.describe(state, data, live, built)
    async with state.db.write() as tx:
        member_id = await member_for(tx.session, session.device_id)
        saved = await service.save(tx.session, data, built, described, member_id, state.clock.now())
        out = await service.trip_out(tx.session, saved.trip)
        if saved.created:
            tx.publish("trip.created", service.trip_event(out, member_id))
        else:
            tx.publish("trip.items", service.trip_event(out, member_id, saved.changed))
        tx.publish("plan.changed")
    if not saved.created:
        response.status_code = 200
    return out


@router.get("/trips")
async def list_trips(
    state: StateDep, session: SessionDep, before: datetime | None = None
) -> TripsOut:
    async with state.db.read() as db:
        return await service.list_trips(db, before)


@router.get("/trips/{trip_id}")
async def get_trip(
    trip_id: str,
    state: StateDep,
    session: SessionDep,
    since_version: Annotated[int | None, Query(ge=0)] = None,
) -> TripOut:
    async with state.db.read() as db:
        return await service.trip_out(db, await service.get_trip(db, trip_id), since_version)


@router.post("/trips/{trip_id}/ops")
async def apply_ops(
    trip_id: str, body: OpsIn, request: Request, state: StateDep, session: SessionDep
) -> OpsOut:
    """A batch of shopping actions (PLAN §9.2). Always 200 once the batch parses; each op says
    what became of it."""
    if int(request.headers.get("content-length") or 0) > MAX_OPS_BYTES:
        raise AppError(413, "too_many_changes", "Too many changes at once. Send fewer.")
    now = state.clock.now()
    async with state.db.write() as tx:
        trip = await service.get_trip(tx.session, trip_id)
        member_id = await member_for(tx.session, session.device_id)
        outcome = await ops.apply(tx.session, trip, body, member_id, now)
        out = await service.trip_out(tx.session, trip, since_version=body.known_version)
        changed = list(outcome.changed.values())
        if changed:
            tx.publish("trip.items", service.trip_event(out, member_id, changed))
        if outcome.header_changed:
            tx.publish("trip.state", service.trip_event(out, member_id))
    if outcome.skew_ms is not None:
        log.info("trip.ops", count=len(body.ops), skew_ms=outcome.skew_ms)
    return OpsOut(
        trip_id=trip_id,
        trip_version=out.version,
        trip_status=out.status,
        server_time=service.ms(state.clock.now()),
        results=outcome.results,
        items=out.items,
        trip=service.header_of(out),
    )


@router.post("/trips/{trip_id}/shop-again", status_code=201)
async def shop_again(trip_id: str, state: StateDep, session: SessionDep) -> TripOut:
    """Shop this again (UX §4.15): the same items as a new saved list, at today's prices."""
    async with state.db.read() as db:
        old = await service.get_trip(db, trip_id)
        old_items = list(
            await db.scalars(
                select(TripItem)
                .where(TripItem.trip_id == old.id, TripItem.removed_at.is_(None))
                .order_by(TripItem.position)
            )
        )
        rows = await service.item_rows(db, [i.item_id for i in old_items if i.item_id])
        store = await active_store(db)
        sections: dict[str, StoreSection] = {}
        if store is not None:
            found = await db.scalars(select(StoreSection).where(StoreSection.store_id == store.id))
            sections = {section.key: section for section in found}
    if not old_items:
        raise AppError(409, "nothing_to_save", "That trip had nothing on it.")
    products = await _live_products(state, rows.values(), store.location_id if store else None)
    now = state.clock.now()
    lines = again.lines_again(
        old_items,
        rows,
        products,
        store,
        sections,
        items.store_zone(state, store),
        now,
        state.catalog.kroger.image_url,
    )
    async with state.db.write() as tx:
        member_id = await member_for(tx.session, session.device_id)
        trip = await again.create(tx.session, lines, store, member_id, now)
        out = await service.trip_out(tx.session, trip)
        tx.publish("trip.created", service.trip_event(out, member_id))
    return out


async def _live_products(
    state: AppState, rows: Iterable[Item], location_id: str | None
) -> dict[str, Product]:
    ids = sorted({row.product_id for row in rows if row.product_id})
    if not ids or location_id is None:
        return {}
    try:
        return await state.catalog.products(ids, location_id)
    except KrogerError:
        return {}  # the new list is saved without prices; they'll show as "no price"
