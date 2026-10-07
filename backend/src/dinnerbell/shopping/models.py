"""Saved lists ("trips"), the items on them, and every shopping action applied (PLAN §5, §9.2).

A trip is a snapshot on purpose: later edits to meals or prices never change a list someone
is shopping from. Only each item's state and note change while shopping, as separate
last-writer-wins fields stamped with corrected phone time (ms); the trip's status is a third.
Every change takes the trip's next version, with no gaps, so phones can catch up by version.
"""

from __future__ import annotations

from datetime import date, datetime
from fractions import Fraction
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import FractionText, UTCDateTime, new_id, utcnow


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="SET NULL"), default=None, index=True
    )
    store_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("stores.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | finished
    status_ts: Mapped[int] = mapped_column(BigInteger, default=0)
    status_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    created_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    estimate_cents: Mapped[int] = mapped_column(Integer, default=0)
    savings_cents: Mapped[int] = mapped_column(Integer, default=0)
    not_priced: Mapped[int] = mapped_column(Integer, default=0)
    prices_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    actual_total_cents: Mapped[int | None] = mapped_column(Integer, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    version: Mapped[int] = mapped_column(Integer, default=0)
    # What the list looked like when saved, to tell when the plan's list has changed since.
    fingerprint: Mapped[str] = mapped_column(String(64), default="")
    # When the copy of Kroger's photos, links and aisles gets cleared (ADR 0016).
    product_cache_expires_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), default=None, index=True
    )


class TripItem(Base):
    __tablename__ = "trip_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    line_key: Mapped[str] = mapped_column(String(64))  # an item id, or "extra:<id>"
    item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("items.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(80))
    product_id: Mapped[str | None] = mapped_column(String(16), default=None)
    upc: Mapped[str | None] = mapped_column(String(16), default=None)
    image_url: Mapped[str | None] = mapped_column(String(300), default=None)
    product_url: Mapped[str | None] = mapped_column(String(300), default=None)
    size_text: Mapped[str | None] = mapped_column(String(80), default=None)
    qty_text: Mapped[str] = mapped_column(String(120))  # "2 boxes, 16 oz each"
    quantity: Mapped[Fraction] = mapped_column(FractionText())
    unit: Mapped[str] = mapped_column(String(8))  # package | each | pound
    unit_cents: Mapped[int | None] = mapped_column(Integer, default=None)
    line_cents: Mapped[int | None] = mapped_column(Integer, default=None)
    regular_cents: Mapped[int | None] = mapped_column(Integer, default=None)
    on_sale: Mapped[bool] = mapped_column(Boolean, default=False)
    sale_ends: Mapped[date | None] = mapped_column(Date, default=None)
    section_key: Mapped[str | None] = mapped_column(String(64), default=None)
    section_label: Mapped[str | None] = mapped_column(String(120), default=None)
    section_order: Mapped[int] = mapped_column(Integer, default=9900)
    aisle_side: Mapped[str | None] = mapped_column(String(1), default=None)  # L | R
    bay: Mapped[int] = mapped_column(Integer, default=0)
    used_by: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(8), default="todo")  # todo | done | missed
    state_ts: Mapped[int] = mapped_column(BigInteger, default=0)
    state_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    note_ts: Mapped[int] = mapped_column(BigInteger, default=0)
    note_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    version: Mapped[int] = mapped_column(Integer, default=0)
    # Taken off by "Update saved list"; kept (with a new version) so other phones hear it.
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)


class AppliedOp(Base):
    """Every shopping action seen, so a resent one is never applied twice (pruned at 60 days)."""

    __tablename__ = "applied_ops"

    op_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24))
    client_id: Mapped[str] = mapped_column(String(64))
    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    client_ts: Mapped[int] = mapped_column(BigInteger)
    effective_ts: Mapped[int] = mapped_column(BigInteger)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    result: Mapped[str] = mapped_column(String(16))  # applied | superseded | rejected
    reason: Mapped[str | None] = mapped_column(String(32), default=None)
