"""Send a saved list to the Kroger cart (PLAN §7.5, UX §5.5).

* **What can go:** items linked to a store product (a UPC), bought in whole packages or pieces.
  Plain-text extras and pound amounts are listed as "add it in the Kroger app": Kroger's cart
  takes whole units, and its docs don't say how it counts a weight, so that isn't guessed.
* **One item per call,** in list order, one at a time, and never retried automatically. Each
  item's row is written as `unknown` before its call goes out and settled after: Kroger's yes
  → added; a 4xx → failed; a timeout, a dropped connection or a 5xx → unknown ("check your
  Kroger cart"). A crash between the two leaves `unknown`, which is the truth.
* **The double-add guard:** an item already `added` or `unknown` is skipped unless the person
  confirmed sending it again (`again`).
* **Sending stops** at the first sign the rest would fail too: Kroger refusing the account or
  the app, its daily limit, or Kroger not answering. The items after it simply weren't sent.
* **One send per saved list at a time,** tracked in memory: one process serves the API (ADR
  0002), which is also why other phones can see which items are still going out.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.core.config import KrogerMode
from dinnerbell.core.errors import AppError
from dinnerbell.core.logging import get_logger
from dinnerbell.household.models import Household, Member
from dinnerbell.kroger.account import AccountStatus, KrogerNotConnectedError
from dinnerbell.kroger.client import (
    CartItem,
    KrogerAuthError,
    KrogerCartUnknownError,
    KrogerCustomerAuthError,
    KrogerDailyLimitError,
    KrogerError,
    KrogerRequestError,
    KrogerUnavailableError,
    Modality,
)
from dinnerbell.kroger.models import KrogerToken
from dinnerbell.shopping.models import CartSend, Trip, TripItem
from dinnerbell.shopping.schemas import (
    CartLineOut,
    CartLineStatus,
    CartOut,
    CartResultOut,
    CartSendIn,
)
from dinnerbell.state import AppState

log = get_logger(__name__)

SENDS_KEPT = timedelta(days=7)
AFTER_FINISH = timedelta(hours=24)


class Outcome(StrEnum):
    ADDED = "added"
    FAILED = "failed"
    UNKNOWN = "unknown"


class Reason(StrEnum):
    """Why a send didn't simply work; stored on the row, shown as plain words."""

    REJECTED = "rejected"  # a 4xx for this item
    UNREACHABLE = "unreachable"  # the request never left
    NO_ANSWER = "no_answer"  # a timeout, a dropped connection or a 5xx
    SIGNED_OUT = "signed_out"  # Kroger refused the account's token
    NOT_ALLOWED = "not_allowed"  # Kroger refused the app (no cart access)
    DAILY_LIMIT = "daily_limit"


SENT_NOTES: dict[str | None, str] = {
    Reason.REJECTED: "Kroger didn't take this item.",
    Reason.UNREACHABLE: "Kroger couldn't be reached.",
    Reason.NO_ANSWER: "No answer from Kroger. Check your Kroger cart before sending it again.",
    Reason.SIGNED_OUT: "Kroger asked to sign in again.",
    Reason.NOT_ALLOWED: "Kroger didn't allow adding to the cart.",
    Reason.DAILY_LIMIT: "Kroger's daily limit was reached.",
    None: "No answer from Kroger. Check your Kroger cart before sending it again.",
}
STOPPED: dict[Reason, str] = {
    Reason.UNREACHABLE: "Kroger couldn't be reached, so the rest weren't sent. Try again in a "
    "few minutes.",
    Reason.NO_ANSWER: "Kroger stopped answering, so the rest weren't sent. Check your Kroger "
    "cart, then try again.",
    Reason.SIGNED_OUT: "Kroger asked to sign in again, so the rest weren't sent. Try again; if "
    "it happens again, reconnect Kroger in Settings.",
    Reason.NOT_ALLOWED: "Kroger didn't allow adding to the cart. Whoever runs Dinner Bell can "
    "check the app's Cart access on the Kroger developer site.",
    Reason.DAILY_LIMIT: "Kroger's daily limit was reached, so the rest weren't sent. Try again "
    "tomorrow.",
}
NO_PRODUCT = "Not linked to a store product. Add it in the Kroger app."
BY_WEIGHT = "Sold by the pound. Add it in the Kroger app."


def cart_quantity(item: TripItem) -> tuple[int | None, str | None]:
    """How many go to the cart, or why the item can't go."""
    if not item.upc:
        return None, NO_PRODUCT
    if item.unit == "pound":
        return None, BY_WEIGHT
    return max(1, math.ceil(item.quantity)), None


async def latest_sends(session: AsyncSession, trip_id: str) -> dict[str, CartSend]:
    rows = await session.scalars(
        select(CartSend).where(CartSend.trip_id == trip_id).order_by(CartSend.sent_at, CartSend.id)
    )
    return {row.trip_item_id: row for row in rows}  # the last one per item wins


async def list_items(session: AsyncSession, trip_id: str) -> list[TripItem]:
    rows = await session.scalars(
        select(TripItem)
        .where(TripItem.trip_id == trip_id, TripItem.removed_at.is_(None))
        .order_by(TripItem.position)
    )
    return list(rows)


async def cart_out(state: AppState, session: AsyncSession, trip: Trip) -> CartOut:
    items = await list_items(session, trip.id)
    latest = await latest_sends(session, trip.id)
    member_ids = {send.sent_by_member_id for send in latest.values() if send.sent_by_member_id}
    names = {
        member.id: member.name
        for member in await session.scalars(select(Member).where(Member.id.in_(member_ids)))
    }
    pending = state.cart_sending.get(trip.id, set())
    lines: list[CartLineOut] = []
    for item in items:
        quantity, why_not = cart_quantity(item)
        send = latest.get(item.id)
        status: CartLineStatus
        if quantity is None:
            status, note = "cannot_send", why_not
        elif item.id in pending:
            status, note = "sending", None
        elif send is None:
            status, note = "ready", None
        elif send.outcome == Outcome.ADDED:
            status, note = "added", None
        elif send.outcome == Outcome.FAILED:
            status, note = "failed", SENT_NOTES.get(send.reason, SENT_NOTES[Reason.REJECTED])
        else:
            status, note = "unknown", SENT_NOTES[None]
        lines.append(
            CartLineOut(
                trip_item_id=item.id,
                name=item.name,
                image_url=item.image_url,
                qty_text=item.qty_text,
                quantity=quantity,
                status=status,
                note=note,
                sent_at=send.sent_at if send and status != "sending" else None,
                sent_by=names.get(send.sent_by_member_id or "")
                if send and status != "sending"
                else None,
            )
        )
    home = await session.get(Household, 1)
    token = await session.get(KrogerToken, 1)
    return CartOut(
        trip_id=trip.id,
        account="connected"
        if token and token.status == AccountStatus.CONNECTED
        else "needs_reconnect"
        if token and token.status == AccountStatus.NEEDS_RECONNECT
        else "disconnected",
        demo=state.settings.kroger_mode is KrogerMode.FAKE,
        modality="DELIVERY" if home and home.default_cart_modality == "DELIVERY" else "PICKUP",
        sending=trip.id in state.cart_sending,
        lines=lines,
    )


# ---- sending ------------------------------------------------------------------------------------


@dataclass
class _Tally:
    added: int = 0
    failed: int = 0
    unknown: int = 0
    skipped: int = 0
    not_sent: int = 0
    stopped: Reason | None = None


async def send(
    state: AppState, trip_id: str, body: CartSendIn, member_id: str | None
) -> CartResultOut:
    if trip_id in state.cart_sending:
        raise AppError(409, "cart_busy", "This list is being sent right now. Wait a moment.")
    # Claimed in the same step as the check, before anything awaits: two taps at once can't
    # both get past it, and the second one then sees what the first one sent.
    pending: set[str] = set()
    state.cart_sending[trip_id] = pending
    try:
        tally = await _send(state, trip_id, body, member_id, pending)
    finally:
        del state.cart_sending[trip_id]
        state.hub.publish("cart.changed", {"trip_id": trip_id})  # sending is over
    log.info(
        "cart.sent",
        added=tally.added,
        failed=tally.failed,
        unknown=tally.unknown,
        skipped=tally.skipped,
        not_sent=tally.not_sent,
        stopped=tally.stopped.value if tally.stopped else None,
    )
    async with state.db.read() as db:
        trip = await db.get(Trip, trip_id)
        assert trip is not None
        cart = await cart_out(state, db, trip)
    return CartResultOut(
        added=tally.added,
        failed=tally.failed,
        unknown=tally.unknown,
        skipped=tally.skipped,
        not_sent=tally.not_sent,
        message=_message(tally),
        cart=cart,
    )


async def _send(
    state: AppState, trip_id: str, body: CartSendIn, member_id: str | None, pending: set[str]
) -> _Tally:
    async with state.db.read() as db:
        trip = await db.get(Trip, trip_id)
        if trip is None:
            raise AppError(404, "trip_not_found", "That saved list couldn't be found.")
        if trip.status != "active":
            raise AppError(
                409,
                "trip_finished",
                "That trip is finished. Shop this again makes a new saved list to send.",
            )
        items = await list_items(db, trip_id)
        latest = await latest_sends(db, trip_id)
    by_id = {item.id: item for item in items}
    unknown_ids = [item_id for item_id in body.item_ids if item_id not in by_id]
    if unknown_ids:
        raise AppError(404, "item_not_found", "Some of those items aren't on this list any more.")
    wanted = set(body.item_ids)
    tally = _Tally()
    queue: list[tuple[TripItem, int]] = []
    for item in items:  # list order, whatever order the phone sent
        if item.id not in wanted:
            continue
        quantity, _why_not = cart_quantity(item)
        if quantity is None:
            continue
        last = latest.get(item.id)
        if last is not None and last.outcome != Outcome.FAILED and not body.again:
            tally.skipped += 1
            continue
        queue.append((item, quantity))
    if not queue:
        return tally
    token = await _access_token(state)
    pending.update(item.id for item, _quantity in queue)
    modality = Modality(body.modality)
    for index, (item, quantity) in enumerate(queue):
        assert item.upc is not None
        send_id = await _record(state, trip_id, item, quantity, modality, member_id)
        outcome, reason = await _add_one(state, token, item.upc, quantity, modality)
        await _settle(state, trip_id, send_id, outcome, reason)
        pending.discard(item.id)
        if outcome is Outcome.ADDED:
            tally.added += 1
        elif outcome is Outcome.FAILED:
            tally.failed += 1
        else:
            tally.unknown += 1
        if reason is not None and reason is not Reason.REJECTED:
            tally.stopped = reason
            tally.not_sent = len(queue) - index - 1
            if reason is Reason.SIGNED_OUT:
                await state.account.forget_access()
            break
    return tally


async def _access_token(state: AppState) -> str:
    try:
        return await state.account.access_token()
    except KrogerNotConnectedError as exc:
        if exc.status is AccountStatus.NEEDS_RECONNECT:
            raise AppError(
                409,
                "kroger_reconnect",
                "Kroger needs you to sign in again. Reconnect Kroger in Settings, then send.",
            ) from None
        raise AppError(
            409, "kroger_not_connected", "Connect Kroger in Settings first, then send."
        ) from None
    except KrogerError:
        raise AppError(
            503, "kroger_unavailable", "Kroger isn't answering right now. Try again in a minute."
        ) from None


async def _record(
    state: AppState,
    trip_id: str,
    item: TripItem,
    quantity: int,
    modality: Modality,
    member_id: str | None,
) -> str:
    """The row goes in as `unknown` before the call: a crash after this reads as "maybe"."""
    async with state.db.write() as tx:
        row = CartSend(
            trip_id=trip_id,
            trip_item_id=item.id,
            upc=item.upc,
            quantity=quantity,
            modality=modality.value,
            sent_at=state.clock.now(),
            sent_by_member_id=member_id,
            outcome=Outcome.UNKNOWN.value,
        )
        tx.session.add(row)
        await tx.session.flush()
        return row.id


async def _add_one(
    state: AppState, token: str, upc: str, quantity: int, modality: Modality
) -> tuple[Outcome, Reason | None]:
    try:
        await state.kroger.add_to_cart(token, [CartItem(upc, quantity, modality)])
    except KrogerCartUnknownError:
        return Outcome.UNKNOWN, Reason.NO_ANSWER
    except KrogerUnavailableError:
        return Outcome.FAILED, Reason.UNREACHABLE
    except KrogerCustomerAuthError:
        return Outcome.FAILED, Reason.SIGNED_OUT
    except KrogerAuthError:
        return Outcome.FAILED, Reason.NOT_ALLOWED
    except KrogerDailyLimitError:
        return Outcome.FAILED, Reason.DAILY_LIMIT
    except KrogerRequestError:
        return Outcome.FAILED, Reason.REJECTED
    except KrogerError:
        return Outcome.UNKNOWN, Reason.NO_ANSWER
    return Outcome.ADDED, None


async def _settle(
    state: AppState, trip_id: str, send_id: str, outcome: Outcome, reason: Reason | None
) -> None:
    async with state.db.write() as tx:
        await tx.session.execute(
            update(CartSend)
            .where(CartSend.id == send_id)
            .values(outcome=outcome.value, reason=reason.value if reason else None)
        )
        tx.publish("cart.changed", {"trip_id": trip_id})


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _message(tally: _Tally) -> str:
    if tally.stopped is not None and tally.stopped is not Reason.REJECTED and not tally.added:
        return STOPPED[tally.stopped]
    parts: list[str] = []
    if tally.added:
        parts.append(f"Added {_plural(tally.added, 'item', 'items')} to your Kroger cart.")
    trouble = tally.failed + tally.unknown
    if trouble:
        parts.append(f"{_plural(trouble, 'item', 'items')} didn't go; see below.")
    if tally.stopped is not None:
        parts.append(STOPPED[tally.stopped])
    if not parts:
        if tally.skipped:
            return "Those items were already sent to your Kroger cart."
        return "Nothing on this list can go to the Kroger cart."
    return " ".join(parts)


# ---- tidying ------------------------------------------------------------------------------------


async def prune(session: AsyncSession, now: datetime) -> None:
    """Kroger's terms: no customer cart data once shopping is done. Keep a send only while it
    still guards against adding twice: a week, or a day after the trip is finished."""
    finished = select(Trip.id).where(
        Trip.status == "finished",
        Trip.finished_at.is_not(None),
        Trip.finished_at <= now - AFTER_FINISH,
    )
    await session.execute(
        delete(CartSend).where(
            or_(CartSend.sent_at < now - SENDS_KEPT, CartSend.trip_id.in_(finished))
        )
    )
