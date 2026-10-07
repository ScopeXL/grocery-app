"""Saved lists: saving the plan's list (or updating the saved one), reading trips and history,
Shop this again, and clearing the copy of Kroger's data once a trip is over (ADR 0016).

Kroger is called only outside write transactions: callers build the list first, then hand it
here inside the transaction.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.catalog.models import Item
from dinnerbell.core.errors import AppError
from dinnerbell.domain import listbuild
from dinnerbell.domain.models import Flag
from dinnerbell.household.models import Member
from dinnerbell.planning.listview import AISLE_ORDER, Placement, PlanData, fingerprint, shoppable
from dinnerbell.planning.schemas import LineOut, MemberRef
from dinnerbell.shopping.models import AppliedOp, Trip, TripItem
from dinnerbell.shopping.schemas import (
    MealUseOut,
    TripHeader,
    TripItemOut,
    TripOut,
    TripsOut,
)
from dinnerbell.stores.models import Store, StoreSection

LATE_OPS = timedelta(hours=24)  # check-offs still count this long after a trip is finished
OPS_KEPT = timedelta(days=60)
HISTORY_PAGE = 20
STEP = 100  # the walking-order editor spaces sections this far apart
SNAPSHOT_FIELDS = (
    "item_id",
    "name",
    "product_id",
    "upc",
    "image_url",
    "product_url",
    "size_text",
    "qty_text",
    "quantity",
    "unit",
    "unit_cents",
    "line_cents",
    "regular_cents",
    "on_sale",
    "sale_ends",
    "section_key",
    "section_label",
    "section_order",
    "aisle_side",
    "bay",
    "used_by",
    "warnings",
    "position",
)


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


# ---- reading ----------------------------------------------------------------------------------


async def get_trip(session: AsyncSession, trip_id: str) -> Trip:
    trip = await session.get(Trip, trip_id)
    if trip is None:
        raise AppError(404, "trip_not_found", "That saved list couldn't be found.")
    return trip


def item_out(item: TripItem) -> TripItemOut:
    return TripItemOut(
        id=item.id,
        line_key=item.line_key,
        item_id=item.item_id,
        name=item.name,
        image_url=item.image_url,
        product_url=item.product_url,
        size_text=item.size_text,
        qty_text=item.qty_text,
        quantity=str(item.quantity),
        unit=item.unit,  # pyright: ignore[reportArgumentType]
        unit_cents=item.unit_cents,
        line_cents=item.line_cents,
        regular_cents=item.regular_cents,
        on_sale=item.on_sale,
        sale_ends=item.sale_ends,
        section_key=item.section_key,
        section_label=item.section_label,
        section_order=item.section_order,
        aisle_side=item.aisle_side,
        bay=item.bay,
        position=item.position,
        used_by=[MealUseOut.model_validate(use) for use in item.used_by],
        warnings=list(item.warnings),
        state=item.state,  # pyright: ignore[reportArgumentType]
        state_ts=item.state_ts,
        state_by=item.state_by_member_id,
        note=item.note,
        note_ts=item.note_ts,
        note_by=item.note_by_member_id,
        version=item.version,
        removed=item.removed_at is not None,
    )


async def headers(session: AsyncSession, trips: Sequence[Trip]) -> list[TripHeader]:
    ids = [trip.id for trip in trips]
    counts: dict[str, dict[str, int]] = {trip_id: {} for trip_id in ids}
    rows = await session.execute(
        select(TripItem.trip_id, TripItem.state, func.count())
        .where(TripItem.trip_id.in_(ids), TripItem.removed_at.is_(None))
        .group_by(TripItem.trip_id, TripItem.state)
    )
    for trip_id, state, count in rows:
        counts[trip_id][state] = count
    store_ids = {trip.store_id for trip in trips if trip.store_id}
    stores = {s.id: s for s in await session.scalars(select(Store).where(Store.id.in_(store_ids)))}
    out: list[TripHeader] = []
    for trip in trips:
        by_state = counts[trip.id]
        store = stores.get(trip.store_id) if trip.store_id else None
        out.append(
            TripHeader(
                id=trip.id,
                status=trip.status,  # pyright: ignore[reportArgumentType]
                version=trip.version,
                plan_id=trip.plan_id,
                store_name=store.name if store else None,
                created_at=trip.created_at,
                created_by=trip.created_by_member_id,
                estimate_cents=trip.estimate_cents,
                savings_cents=trip.savings_cents,
                not_priced=trip.not_priced,
                prices_as_of=trip.prices_as_of,
                actual_total_cents=trip.actual_total_cents,
                finished_at=trip.finished_at,
                status_by=trip.status_by_member_id,
                status_ts=trip.status_ts,
                item_count=sum(by_state.values()),
                done_count=by_state.get("done", 0),
                missed_count=by_state.get("missed", 0),
            )
        )
    return out


async def trip_out(session: AsyncSession, trip: Trip, since_version: int | None = None) -> TripOut:
    statement = select(TripItem).where(TripItem.trip_id == trip.id)
    if since_version is not None:
        statement = statement.where(TripItem.version > since_version)
    else:
        statement = statement.where(TripItem.removed_at.is_(None))
    found = list(await session.scalars(statement.order_by(TripItem.position, TripItem.id)))
    members = await session.scalars(select(Member).order_by(Member.sort, Member.created_at))
    [header] = await headers(session, [trip])
    return TripOut(
        **header.model_dump(),
        members=[MemberRef(id=m.id, name=m.name, marker_color=m.marker_color) for m in members],
        items=[item_out(item) for item in found],
        complete=since_version is None,
    )


def header_of(trip: TripOut) -> TripHeader:
    return TripHeader.model_validate(trip.model_dump(include=set(TripHeader.model_fields)))


async def list_trips(session: AsyncSession, before: datetime | None) -> TripsOut:
    active = list(
        await session.scalars(
            select(Trip).where(Trip.status == "active").order_by(Trip.created_at.desc())
        )
    )
    statement = select(Trip).where(Trip.status == "finished")
    if before is not None:
        statement = statement.where(Trip.finished_at < before)
    finished = list(
        await session.scalars(statement.order_by(Trip.finished_at.desc()).limit(HISTORY_PAGE + 1))
    )
    return TripsOut(
        active=await headers(session, active),
        finished=await headers(session, finished[:HISTORY_PAGE]),
        more=len(finished) > HISTORY_PAGE,
    )


async def active_trip_for(session: AsyncSession, plan_id: str) -> Trip | None:
    return await session.scalar(
        select(Trip)
        .where(Trip.plan_id == plan_id, Trip.status == "active")
        .order_by(Trip.created_at.desc())
        .limit(1)
    )


def trip_event(
    trip: TripOut, by: str | None, changed: list[TripItem] | None = None
) -> dict[str, Any]:
    """A trip event's payload: the header as it is now, and what changed (PLAN §9.3)."""
    payload: dict[str, Any] = {
        "trip_id": trip.id,
        "trip_version": trip.version,
        "by": by,
        "trip": header_of(trip).model_dump(mode="json"),
    }
    if changed is not None:
        payload["items"] = [item_out(item).model_dump(mode="json") for item in changed]
    return payload


async def resort(
    session: AsyncSession, store_id: str, orders: Mapping[str, int]
) -> list[tuple[Trip, list[TripItem]]]:
    """Lists being shopped at this store follow a new walking order."""
    out: list[tuple[Trip, list[TripItem]]] = []
    trips = await session.scalars(
        select(Trip).where(Trip.store_id == store_id, Trip.status == "active")
    )
    for trip in trips:
        changed: list[TripItem] = []
        found = await session.scalars(
            select(TripItem).where(TripItem.trip_id == trip.id, TripItem.removed_at.is_(None))
        )
        for item in found:
            order = orders.get(item.section_key or "")
            if order is not None and order != item.section_order:
                item.section_order = order
                bump(trip, item)
                changed.append(item)
        if changed:
            out.append((trip, changed))
    await session.flush()
    return out


# ---- saving the plan's list -------------------------------------------------------------------


@dataclass
class Saved:
    trip: Trip
    created: bool
    changed: list[TripItem]  # items that took a new version


def bump(trip: Trip, item: TripItem | None = None) -> None:
    """Every change takes the trip's next version, so phones can catch up with no gaps."""
    trip.version += 1
    if item is not None:
        item.version = trip.version


def snapshot(
    line: LineOut, placement: Placement, built: listbuild.Line, data: PlanData
) -> dict[str, Any]:
    """A list line, frozen for shopping (PLAN §5: a trip is a snapshot on purpose)."""
    row = data.items.get(line.item_id) if line.item_id else None
    override = data.overrides.get(line.item_id) if line.item_id else None
    swapped = override is not None and override.swap_product_id == built.product_id
    upc = (override.swap_upc if override and swapped else None) or (row.upc if row else None)
    notes = [
        extra.note
        for extra in data.extras
        if extra.note
        and ((extra.item_id and extra.item_id == line.item_id) or line.key == f"extra:{extra.id}")
    ]
    return {
        "item_id": line.item_id,
        "name": line.name,
        "product_id": built.product_id,
        "upc": upc if built.product_id else None,
        "image_url": line.image_url,
        "product_url": line.product_url,
        "size_text": line.size_text,
        "qty_text": line.amount_text,
        "quantity": built.quantity,
        "unit": built.unit.value,
        "unit_cents": built.unit_cents,
        "line_cents": line.cost_cents,
        "regular_cents": line.regular_cents,
        "on_sale": Flag.ON_SALE in built.flags,
        "sale_ends": line.sale.ends if line.sale else None,
        "section_key": line.section.key,
        "section_label": line.section.label,
        "section_order": line.section.order,
        "aisle_side": placement.side,
        "bay": placement.bay,
        "used_by": [{"meal_id": use.meal_id, "name": use.name} for use in line.used_by],
        "warnings": [warning for warning in line.warnings if warning != "No price"],
        "note": "; ".join(notes)[:200] or None,
    }


async def save(
    session: AsyncSession,
    data: PlanData,
    built: listbuild.ShoppingList,
    described: Sequence[tuple[LineOut, Placement]],
    member_id: str | None,
    now: datetime,
) -> Saved:
    """Save the plan's list, or bring its saved list up to date: changed lines take the new
    amounts and prices; new lines join as to-do; lines no longer needed leave the list unless
    someone already checked them off or couldn't find them. Shoppers' states and notes stay."""
    if data.plan is None:
        raise AppError(409, "nothing_to_save", "Plan a meal or add something first.")
    by_key = {line.key: line for line in built.lines}
    lines = [(line, place) for line, place in described if shoppable(by_key[line.key])]
    if not lines:
        raise AppError(409, "nothing_to_save", "There's nothing to buy yet.")
    orders = await ensure_aisles(session, data.store, (place for _line, place in lines))

    trip = await active_trip_for(session, data.plan.id)
    created = trip is None
    if trip is None:
        trip = Trip(
            plan_id=data.plan.id,
            store_id=data.store.id if data.store else None,
            status="active",
            status_ts=ms(now),
            status_by_member_id=member_id,
            created_by_member_id=member_id,
            created_at=now,
            version=0,
        )
        session.add(trip)
        await session.flush()
    existing = {
        item.line_key: item
        for item in await session.scalars(
            select(TripItem).where(TripItem.trip_id == trip.id, TripItem.removed_at.is_(None))
        )
    }
    changed: list[TripItem] = []
    for position, (line, place) in enumerate(lines):
        values = snapshot(line, place, by_key[line.key], data)
        values["position"] = position
        values["section_order"] = orders.get(place.key, values["section_order"])
        note = values.pop("note")
        item = existing.pop(line.key, None)
        if item is None:
            item = TripItem(trip_id=trip.id, line_key=line.key, note=note, **values)
            session.add(item)
        else:
            differs = [field for field in SNAPSHOT_FIELDS if getattr(item, field) != values[field]]
            plan_note = item.note_ts == 0 and item.note != note  # a shopper's note stays
            if not differs and not plan_note:
                continue
            for field in differs:
                setattr(item, field, values[field])
            if plan_note:
                item.note = note
        bump(trip, item)
        changed.append(item)
    for item in existing.values():  # no longer on the list
        if item.state == "todo":
            item.removed_at = now
            bump(trip, item)
            changed.append(item)

    totals = built.totals
    trip.estimate_cents = totals.total
    trip.savings_cents = totals.savings
    trip.not_priced = totals.not_priced
    trip.prices_as_of = totals.prices_as_of
    trip.fingerprint = fingerprint(built.lines)
    bump(trip)
    await session.flush()
    return Saved(trip, created, changed)


async def ensure_aisles(
    session: AsyncSession, store: Store | None, places: Iterable[Placement]
) -> dict[str, int]:
    """Give every aisle on a saved list a section, so the walking-order editor can move it.

    New aisles walk in number order. Once the household has moved aisles around, a new one
    walks just after the nearest lower-numbered aisle (or before the nearest higher one).
    Returns the walking order of every aisle section.
    """
    if store is None:
        return {}
    sections = {
        section.key: section
        for section in await session.scalars(
            select(StoreSection).where(StoreSection.store_id == store.id)
        )
    }
    placed = {n: s.sort_index for key, s in sections.items() if (n := _aisle(key)) is not None}
    moved = any(order != AISLE_ORDER + n for n, order in placed.items())
    for place in places:
        number = _aisle(place.key)
        if number is None or place.key in sections:
            continue
        below = [n for n in placed if n < number]
        above = [n for n in placed if n > number]
        if moved and below:
            order = placed[max(below)] + min(number - max(below), STEP - 1)
        elif moved and above:
            order = placed[min(above)] - min(min(above) - number, STEP - 1)
        else:
            order = AISLE_ORDER + number
        label = place.label.split(",")[0]
        section = StoreSection(store_id=store.id, key=place.key, label=label, sort_index=order)
        session.add(section)
        sections[place.key] = section
    return {key: s.sort_index for key, s in sections.items() if key.startswith("aisle:")}


def _aisle(key: str) -> int | None:
    if not key.startswith("aisle:"):
        return None
    number = key.removeprefix("aisle:")
    return int(number) if number.isdigit() else None


# ---- after a trip -----------------------------------------------------------------------------


async def clear_kroger_copies(session: AsyncSession, now: datetime) -> int:
    """ADR 0016: once a finished trip's window passes, drop its copy of Kroger's photos, links
    and aisles. Names, amounts, estimates and totals stay; History works without them."""
    trips = list(
        await session.scalars(
            select(Trip).where(
                Trip.status == "finished",
                Trip.product_cache_expires_at.is_not(None),
                Trip.product_cache_expires_at <= now,
            )
        )
    )
    for trip in trips:
        await session.execute(
            update(TripItem)
            .where(TripItem.trip_id == trip.id)
            .values(
                image_url=None,
                product_url=None,
                section_key=None,
                section_label=None,
                section_order=9900,
                aisle_side=None,
                bay=0,
                warnings=[],
            )
        )
        trip.product_cache_expires_at = None
    return len(trips)


async def prune_ops(session: AsyncSession, now: datetime) -> None:
    """Forget phone actions after 60 days; by then no phone still holds them."""
    await session.execute(delete(AppliedOp).where(AppliedOp.received_at < now - OPS_KEPT))


async def item_rows(session: AsyncSession, ids: Iterable[str]) -> Mapping[str, Item]:
    found = await session.scalars(select(Item).where(Item.id.in_(set(ids))))
    return {row.id: row for row in found}
