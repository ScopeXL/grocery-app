"""Saved lists and shopping actions as the API sends them (PLAN §9.2, UX §4.12 to §4.15).

Times a phone stamps are integer milliseconds of corrected time (`client_ts`); every other
time is an ISO datetime. Members are referenced by id, with the household's members listed
on each trip, so a phone can show "Checked off by Mia" offline.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from dinnerbell.planning.schemas import MemberRef, PurchaseUnitName

TripStatus = Literal["active", "finished"]
ItemState = Literal["todo", "done", "missed"]
OpStatus = Literal["applied", "superseded", "duplicate", "rejected"]
MAX_OPS = 100
MAX_OPS_BYTES = 64 * 1024
NOTE_MAX = 200


class MealUseOut(BaseModel):
    meal_id: str
    name: str  # the Main's name, for "By meal" and "for Tacos"


class TripItemOut(BaseModel):
    id: str
    line_key: str  # the list line it came from: an item id, or "extra:<id>"
    item_id: str | None
    name: str
    image_url: str | None  # cleared once the trip is over (ADR 0016)
    product_url: str | None  # "Open in Kroger"
    size_text: str | None
    qty_text: str  # "2 boxes, 16 oz each"
    quantity: str
    unit: PurchaseUnitName
    unit_cents: int | None
    line_cents: int | None  # the estimate for this line
    regular_cents: int | None
    on_sale: bool
    sale_ends: date | None
    section_key: str | None
    section_label: str | None  # "Produce", "Aisle 12, left side"
    section_order: int  # the store's walking order
    aisle_side: str | None  # "L" or "R"
    bay: int  # shelf position within an aisle
    position: int  # the list's order when saved
    used_by: list[MealUseOut]
    warnings: list[str]
    state: ItemState
    state_ts: int
    state_by: str | None  # member id
    note: str | None
    note_ts: int
    note_by: str | None
    version: int
    removed: bool  # taken off when the saved list was updated


class TripHeader(BaseModel):
    id: str
    status: TripStatus
    version: int
    plan_id: str | None
    store_name: str | None
    created_at: datetime
    created_by: str | None
    estimate_cents: int
    savings_cents: int
    not_priced: int
    prices_as_of: datetime | None
    actual_total_cents: int | None
    finished_at: datetime | None
    status_by: str | None  # who finished or reopened it
    status_ts: int
    item_count: int  # on the list now
    done_count: int  # checked off
    missed_count: int  # couldn't find


class TripOut(TripHeader):
    members: list[MemberRef]  # everyone a trip item might name
    items: list[TripItemOut]  # every item, or only those changed since `since_version`
    complete: bool  # false when `items` is only what changed since `since_version`


class TripsOut(BaseModel):
    active: list[TripHeader]  # newest first
    finished: list[TripHeader]  # newest first, a page at a time
    more: bool  # older finished trips exist (ask with `before`)


class FinishIn(BaseModel):
    actual_total_cents: Annotated[int, Field(ge=0, le=10_000_000)] | None = None


class OpIn(BaseModel):
    """One shopping action. Values are absolute (never toggles), so replays are harmless.

    `v` is the op schema version: the server keeps accepting every version ever shipped.
    """

    model_config = ConfigDict(extra="ignore")

    op_id: Annotated[str, StringConstraints(min_length=8, max_length=36)]
    v: int = 1
    kind: Annotated[str, StringConstraints(max_length=32)]
    item_id: Annotated[str, StringConstraints(max_length=36)] | None = None
    state: Annotated[str, StringConstraints(max_length=16)] | None = None
    note: Annotated[str, StringConstraints(max_length=NOTE_MAX)] | None = None
    actual_total_cents: Annotated[int, Field(ge=0, le=10_000_000)] | None = None
    client_ts: Annotated[int, Field(ge=0)]
    client_seq: Annotated[int, Field(ge=0)] = 0


class OpsIn(BaseModel):
    client_id: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    known_version: Annotated[int, Field(ge=0)] = 0
    ops: list[OpIn] = Field(max_length=MAX_OPS)


class OpResultOut(BaseModel):
    op_id: str
    status: OpStatus
    original: Literal["applied", "superseded", "rejected"] | None = None  # for a duplicate
    reason: str | None = None  # for a rejection: unknown_item, trip_closed, unknown_kind …


class OpsOut(BaseModel):
    trip_id: str
    trip_version: int
    trip_status: TripStatus
    server_time: int  # ms
    results: list[OpResultOut]
    items: list[TripItemOut]  # every item with a version above `known_version`
    trip: TripHeader  # the header as it is now
