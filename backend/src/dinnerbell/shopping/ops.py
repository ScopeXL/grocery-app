"""Applying shopping actions sent by phones, possibly long after they happened (PLAN §9.2).

* **Idempotent.** Every op_id is recorded; a resent op returns its first result, unchanged.
* **Last writer wins, per field.** An item's state and its note, and the trip's status, are
  separate registers. Each holds the corrected phone time of the action that set it, and an
  action applies only if it's at least as new (ties go to the later arrival). Phones can't
  claim the future: an action's time is clamped to when the server received it.
* **Late check-offs count.** Item actions still apply for 24 hours after a trip is finished
  elsewhere, because someone offline really did put those things in the cart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.shopping.models import AppliedOp, Trip, TripItem
from dinnerbell.shopping.schemas import OpIn, OpResultOut, OpsIn
from dinnerbell.shopping.service import LATE_OPS, bump, ms

OP_VERSIONS = {1}
STATES = {"todo", "done", "missed"}
ITEM_KINDS = {"item.set_state", "item.set_note"}


@dataclass
class Outcome:
    results: list[OpResultOut] = field(default_factory=list[OpResultOut])
    changed: dict[str, TripItem] = field(default_factory=dict[str, TripItem])  # by item id
    header_changed: bool = False
    skew_ms: int | None = None  # the newest action's time minus arrival (clock skew, logged)


async def apply(
    session: AsyncSession,
    trip: Trip,
    body: OpsIn,
    member_id: str | None,
    received_at: datetime,
) -> Outcome:
    arrived = ms(received_at)
    ids = [op.op_id for op in body.ops]
    seen = {
        row.op_id: row
        for row in await session.scalars(select(AppliedOp).where(AppliedOp.op_id.in_(ids)))
    }
    items = {
        item.id: item
        for item in await session.scalars(select(TripItem).where(TripItem.trip_id == trip.id))
    }
    outcome = Outcome()
    for op in sorted(body.ops, key=lambda op: op.client_seq):
        prior = seen.get(op.op_id)
        if prior is not None:
            outcome.results.append(
                OpResultOut(
                    op_id=op.op_id,
                    status="duplicate",
                    original=prior.result,  # pyright: ignore[reportArgumentType]
                    reason=prior.reason,
                )
            )
            continue
        effective = min(op.client_ts, arrived)
        if outcome.skew_ms is None or op.client_ts - arrived > outcome.skew_ms:
            outcome.skew_ms = op.client_ts - arrived
        status, reason = _apply_one(trip, items, op, effective, member_id, received_at, outcome)
        record = AppliedOp(
            op_id=op.op_id,
            trip_id=trip.id,
            kind=op.kind[:24],
            client_id=body.client_id,
            member_id=member_id,
            client_ts=op.client_ts,
            effective_ts=effective,
            received_at=received_at,
            result=status,
            reason=reason,
        )
        session.add(record)
        seen[op.op_id] = record  # the same op twice in one batch is a duplicate too
        outcome.results.append(OpResultOut(op_id=op.op_id, status=status, reason=reason))  # pyright: ignore[reportArgumentType]
    await session.flush()
    return outcome


def _apply_one(
    trip: Trip,
    items: dict[str, TripItem],
    op: OpIn,
    effective: int,
    member_id: str | None,
    received_at: datetime,
    outcome: Outcome,
) -> tuple[str, str | None]:
    if op.v not in OP_VERSIONS:
        return "rejected", "unknown_version"
    if op.kind in ITEM_KINDS:
        item = items.get(op.item_id or "")
        if item is None or item.removed_at is not None:
            return "rejected", "unknown_item"
        if trip.status == "finished" and trip.finished_at is not None:
            if received_at - trip.finished_at > LATE_OPS:
                return "rejected", "trip_closed"
        if op.kind == "item.set_state":
            if op.state not in STATES:
                return "rejected", "bad_state"
            if effective < item.state_ts:
                return "superseded", None
            item.state, item.state_ts, item.state_by_member_id = op.state, effective, member_id
        else:
            if effective < item.note_ts:
                return "superseded", None
            note = (op.note or "").strip() or None
            item.note, item.note_ts, item.note_by_member_id = note, effective, member_id
        bump(trip, item)
        outcome.changed[item.id] = item
        return "applied", None
    if op.kind == "trip.finish":
        if trip.status == "finished":
            # Finished twice: the first finish stands, but it can still learn what was paid.
            if trip.actual_total_cents is None and op.actual_total_cents is not None:
                trip.actual_total_cents = op.actual_total_cents
                bump(trip)
                outcome.header_changed = True
            return "superseded", None
        if effective < trip.status_ts:
            return "superseded", None
        trip.status, trip.status_ts, trip.status_by_member_id = "finished", effective, member_id
        trip.finished_at = received_at
        trip.product_cache_expires_at = received_at + LATE_OPS
        if op.actual_total_cents is not None:
            trip.actual_total_cents = op.actual_total_cents
        bump(trip)
        outcome.header_changed = True
        return "applied", None
    if op.kind == "trip.reopen":
        if trip.status == "active" or effective < trip.status_ts:
            return "superseded", None
        trip.status, trip.status_ts, trip.status_by_member_id = "active", effective, member_id
        trip.finished_at = None
        trip.product_cache_expires_at = None
        bump(trip)
        outcome.header_changed = True
        return "applied", None
    return "rejected", "unknown_kind"
