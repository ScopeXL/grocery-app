"""Send to Kroger cart (PLAN §7.5, UX §5.5) against sample mode's cart. Synthetic data only.

The idempotency tests: nothing is ever retried automatically, an item already added (or maybe
added) never goes again without `again`, and an unclear answer reads as "check your cart".
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from dinnerbell.core.clock import FakeClock
from dinnerbell.kroger.client import (
    CartItem,
    KrogerCartUnknownError,
    KrogerCustomerAuthError,
    KrogerDailyLimitError,
    KrogerGrantError,
    KrogerRequestError,
    Modality,
)
from dinnerbell.kroger.fake import FakeKroger
from dinnerbell.kroger.models import KrogerToken
from dinnerbell.shopping import cart
from dinnerbell.shopping.models import CartSend
from dinnerbell.state import AppState
from tests.kroger.test_account import connect
from tests.support import CSRF
from tests.test_planning import BEANS, BEEF, CHEDDAR, SHELLS, plan_meal, taco_night

NOW_MS = 1791295200000  # 2026-10-06T14:00:00Z


def app_state(app: FastAPI) -> AppState:
    return app.state.dinnerbell


def fake(app: FastAPI) -> FakeKroger:
    kroger = app_state(app).kroger
    assert isinstance(kroger, FakeKroger)
    return kroger


@pytest.fixture
async def trip(shopper: httpx.AsyncClient) -> dict[str, Any]:
    """Tacos and Chili saved as a list: beef, shells, cheddar, beans, and onion by the pound."""
    ids = await taco_night(shopper)
    await plan_meal(shopper, ids["tacos"])
    await plan_meal(shopper, ids["chili"])
    response = await shopper.post("/api/trips", headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()


def ids(trip: dict[str, Any], *names: str) -> list[str]:
    by_name = {item["name"]: item["id"] for item in trip["items"]}
    return [by_name[name] for name in names] if names else list(by_name.values())


def lines(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {line["name"]: line for line in body["lines"]}


async def get_cart(client: httpx.AsyncClient, trip_id: str) -> dict[str, Any]:
    response = await client.get(f"/api/trips/{trip_id}/cart")
    assert response.status_code == 200, response.text
    return response.json()


async def send(
    client: httpx.AsyncClient,
    trip_id: str,
    item_ids: Sequence[str],
    *,
    modality: str = "PICKUP",
    again: bool = False,
    status: int = 200,
) -> dict[str, Any]:
    response = await client.post(
        f"/api/trips/{trip_id}/send-to-cart",
        json={"modality": modality, "item_ids": list(item_ids), "again": again},
        headers=CSRF,
    )
    assert response.status_code == status, response.text
    return response.json()


def in_cart(app: FastAPI) -> list[tuple[str, int, str]]:
    return [(item.upc, item.quantity, item.modality.value) for item in fake(app).cart]


SENDABLE = ("Ground beef", "Taco shells", "Shredded cheddar", "Black beans")
UPCS = {
    "Ground beef": BEEF,
    "Taco shells": SHELLS,
    "Shredded cheddar": CHEDDAR,
    "Black beans": BEANS,
}
QUANTITIES = {"Ground beef": 2, "Taco shells": 1, "Shredded cheddar": 1, "Black beans": 2}


def walk(trip: dict[str, Any]) -> list[str]:
    """What can go, in the saved list's order (its store walking order)."""
    return [item["name"] for item in trip["items"] if item["name"] in UPCS]


# ---- what can go -----------------------------------------------------------------------------


async def test_the_cart_shows_what_can_go_and_what_cant(
    shopper: httpx.AsyncClient, trip: dict[str, Any]
) -> None:
    body = await get_cart(shopper, trip["id"])
    assert (body["account"], body["demo"], body["modality"], body["sending"]) == (
        "disconnected",
        True,
        "PICKUP",
        False,
    )
    found = lines(body)
    assert [line["name"] for line in body["lines"]] == [i["name"] for i in trip["items"]]
    assert {name: (line["status"], line["quantity"]) for name, line in found.items()} == {
        "Ground beef": ("ready", 2),
        "Taco shells": ("ready", 1),
        "Shredded cheddar": ("ready", 1),
        "Black beans": ("ready", 2),
        "Yellow onion": ("cannot_send", None),
    }
    assert found["Yellow onion"]["note"] == "Sold by the pound. Add it in the Kroger app."


async def test_plain_text_extras_cant_go(shopper: httpx.AsyncClient) -> None:
    await shopper.post("/api/plan/extras", json={"text": "Birthday candles"}, headers=CSRF)
    saved = (await shopper.post("/api/trips", headers=CSRF)).json()
    candles = lines(await get_cart(shopper, saved["id"]))["Birthday candles"]
    assert (candles["status"], candles["quantity"]) == ("cannot_send", None)
    assert candles["note"] == "Not linked to a store product. Add it in the Kroger app."


async def test_sending_needs_a_connected_account(
    shopper: httpx.AsyncClient, trip: dict[str, Any]
) -> None:
    body = await send(shopper, trip["id"], ids(trip), status=409)
    assert body["error"] == {
        "code": "kroger_not_connected",
        "message": "Connect Kroger in Settings first, then send.",
    }


# ---- sending ---------------------------------------------------------------------------------


async def test_send_adds_each_item_once_and_says_so(
    shopper: httpx.AsyncClient,
    trip: dict[str, Any],
    app: FastAPI,
    events: list[tuple[str, dict[str, Any]]],
) -> None:
    await connect(shopper)
    result = await send(shopper, trip["id"], ids(trip))
    assert (result["added"], result["failed"], result["unknown"], result["skipped"]) == (4, 0, 0, 0)
    assert result["message"] == "Added 4 items to your Kroger cart."
    assert in_cart(app) == [(UPCS[name], QUANTITIES[name], "PICKUP") for name in walk(trip)]
    sent = lines(result["cart"])
    assert {name: sent[name]["status"] for name in SENDABLE} == dict.fromkeys(SENDABLE, "added")
    assert sent["Ground beef"]["sent_by"] == "Sample Parent"
    assert sent["Ground beef"]["sent_at"].startswith("2026-10-06T14:00")
    assert ("cart.changed", {"trip_id": trip["id"]}) in events


async def test_sending_again_skips_what_is_already_in_the_cart(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    """The double-add guard: the phone checklist's "Send again" says they were already sent."""
    await connect(shopper)
    await send(shopper, trip["id"], ids(trip))
    again = await send(shopper, trip["id"], ids(trip))
    assert (again["added"], again["skipped"]) == (0, 4)
    assert again["message"] == "Those items were already sent to your Kroger cart."
    assert len(fake(app).cart) == 4


async def test_send_again_anyway_sends_them_again(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    await connect(shopper)
    await send(shopper, trip["id"], ids(trip))
    result = await send(shopper, trip["id"], ids(trip, "Taco shells"), again=True)
    assert (result["added"], result["skipped"]) == (1, 0)
    assert in_cart(app)[-1] == (SHELLS, 1, "PICKUP")
    assert len(fake(app).cart) == 5


async def test_delivery_goes_as_chosen_without_changing_the_default(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    await connect(shopper)
    await send(shopper, trip["id"], ids(trip, "Black beans"), modality="DELIVERY")
    assert in_cart(app) == [(BEANS, 2, "DELIVERY")]
    assert (await get_cart(shopper, trip["id"]))["modality"] == "PICKUP"
    await shopper.patch("/api/settings", json={"cart_modality": "DELIVERY"}, headers=CSRF)
    assert (await get_cart(shopper, trip["id"]))["modality"] == "DELIVERY"


async def test_items_go_in_list_order_whatever_order_they_were_asked_in(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    await connect(shopper)
    first, *_middle, last = walk(trip)
    await send(shopper, trip["id"], ids(trip, last, first))
    assert [upc for upc, _q, _m in in_cart(app)] == [UPCS[first], UPCS[last]]


async def test_what_cant_go_is_left_out_quietly(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    await connect(shopper)
    result = await send(shopper, trip["id"], ids(trip, "Yellow onion"))
    assert (result["added"], result["skipped"]) == (0, 0)
    assert result["message"] == "Nothing on this list can go to the Kroger cart."
    assert fake(app).cart == []


# ---- when Kroger says no, or nothing ---------------------------------------------------------


async def test_a_refused_item_fails_alone_and_can_go_again(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    await connect(shopper)
    fake(app).cart_failures[SHELLS] = KrogerRequestError(400)
    result = await send(shopper, trip["id"], ids(trip))
    assert (result["added"], result["failed"], result["not_sent"]) == (3, 1, 0)
    assert result["message"] == "Added 3 items to your Kroger cart. 1 item didn't go; see below."
    shells = lines(result["cart"])["Taco shells"]
    assert (shells["status"], shells["note"]) == ("failed", "Kroger didn't take this item.")
    # A failed item is safe to send again (Kroger said no), so it goes without `again`.
    del fake(app).cart_failures[SHELLS]
    retry = await send(shopper, trip["id"], ids(trip, "Taco shells"))
    assert (retry["added"], retry["skipped"]) == (1, 0)
    assert len(fake(app).cart) == 4


async def test_no_answer_means_maybe_and_stops_the_rest(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    await connect(shopper)
    first, second, third, fourth = walk(trip)
    fake(app).cart_failures[UPCS[second]] = KrogerCartUnknownError("timeout")
    result = await send(shopper, trip["id"], ids(trip))
    assert (result["added"], result["unknown"], result["not_sent"]) == (1, 1, 2)
    assert result["message"] == (
        "Added 1 item to your Kroger cart. 1 item didn't go; see below. Kroger stopped "
        "answering, so the rest weren't sent. Check your Kroger cart, then try again."
    )
    found = lines(result["cart"])
    assert [found[name]["status"] for name in (first, second, third, fourth)] == [
        "added",
        "unknown",
        "ready",
        "ready",
    ]
    assert found[second]["note"] == (
        "No answer from Kroger. Check your Kroger cart before sending it again."
    )
    # "Maybe in the cart" is never sent again by itself...
    del fake(app).cart_failures[UPCS[second]]
    rest = await send(shopper, trip["id"], ids(trip))
    assert (rest["added"], rest["skipped"]) == (2, 2)
    assert [upc for upc, _q, _m in in_cart(app)] == [UPCS[n] for n in (first, third, fourth)]
    # ...only when the person says so (Send these again).
    sure = await send(shopper, trip["id"], ids(trip, second), again=True)
    assert sure["added"] == 1


async def test_nothing_is_ever_retried(
    shopper: httpx.AsyncClient,
    trip: dict[str, Any],
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await connect(shopper)
    kroger = fake(app)
    calls: list[str] = []
    original = kroger.add_to_cart

    async def counted(access_token: str, items: Sequence[CartItem]) -> None:
        calls.extend(item.upc for item in items)
        await original(access_token, items)

    monkeypatch.setattr(kroger, "add_to_cart", counted)
    first, second, third, _fourth = walk(trip)
    kroger.cart_failures[UPCS[first]] = KrogerRequestError(400)
    kroger.cart_failures[UPCS[third]] = KrogerCartUnknownError("timeout")
    await send(shopper, trip["id"], ids(trip))
    assert calls == [UPCS[first], UPCS[second], UPCS[third]]  # one each; the last never went


async def test_a_crash_mid_send_reads_as_maybe(
    shopper: httpx.AsyncClient,
    trip: dict[str, Any],
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The row is written before the call, so whatever happens next can't read as "not sent"."""
    await connect(shopper)

    async def broken(access_token: str, items: Sequence[CartItem]) -> None:
        raise RuntimeError("the process died here")

    monkeypatch.setattr(fake(app), "add_to_cart", broken)
    with pytest.raises(RuntimeError):
        await send(shopper, trip["id"], ids(trip))
    found = lines(await get_cart(shopper, trip["id"]))
    first, second, *_rest = walk(trip)
    assert (found[first]["status"], found[second]["status"]) == ("unknown", "ready")
    assert app_state(app).cart_sending == {}


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (
            KrogerDailyLimitError,
            "Kroger's daily limit was reached, so the rest weren't sent. Try again tomorrow.",
        ),
        (
            KrogerCustomerAuthError,
            "Kroger asked to sign in again, so the rest weren't sent. Try again; if it happens "
            "again, reconnect Kroger in Settings.",
        ),
    ],
)
async def test_a_problem_with_every_item_stops_at_the_first(
    shopper: httpx.AsyncClient,
    trip: dict[str, Any],
    app: FastAPI,
    clock: FakeClock,
    failure: type[Exception],
    message: str,
) -> None:
    await connect(shopper)
    error = (
        failure(clock.now() + timedelta(hours=3))
        if failure is KrogerDailyLimitError
        else (failure("no"))
    )
    fake(app).cart_failures[UPCS[walk(trip)[0]]] = error  # pyright: ignore[reportArgumentType]
    result = await send(shopper, trip["id"], ids(trip))
    assert (result["failed"], result["not_sent"], result["message"]) == (1, 3, message)


async def test_a_refused_token_is_refreshed_before_the_next_send(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    await connect(shopper)
    first = UPCS[walk(trip)[0]]
    fake(app).cart_failures[first] = KrogerCustomerAuthError("no")
    await send(shopper, trip["id"], ids(trip))
    async with app_state(app).db.read() as db:
        row = await db.get(KrogerToken, 1)
    assert row is not None and row.access_expires_at is None
    del fake(app).cart_failures[first]
    result = await send(shopper, trip["id"], ids(trip))
    assert result["added"] == 4


async def test_a_lost_account_asks_to_reconnect(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI, clock: FakeClock
) -> None:
    await connect(shopper)
    fake(app).refresh_failure = KrogerGrantError("expired")
    clock.advance(minutes=31)
    body = await send(shopper, trip["id"], ids(trip), status=409)
    assert body["error"]["code"] == "kroger_reconnect"
    assert (await get_cart(shopper, trip["id"]))["account"] == "needs_reconnect"


# ---- one at a time, on the right list --------------------------------------------------------


async def test_one_send_per_list_at_a_time(
    shopper: httpx.AsyncClient,
    trip: dict[str, Any],
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await connect(shopper)
    kroger = fake(app)
    original = kroger.add_to_cart
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(access_token: str, items: Sequence[CartItem]) -> None:
        started.set()
        await release.wait()
        await original(access_token, items)

    monkeypatch.setattr(kroger, "add_to_cart", slow)
    first = asyncio.create_task(send(shopper, trip["id"], ids(trip)))
    await started.wait()
    busy = await send(shopper, trip["id"], ids(trip), status=409)
    assert busy["error"]["code"] == "cart_busy"
    during = await get_cart(shopper, trip["id"])
    assert during["sending"] is True
    assert {lines(during)[name]["status"] for name in SENDABLE} == {"sending"}
    release.set()
    assert (await first)["added"] == 4
    assert (await get_cart(shopper, trip["id"]))["sending"] is False


async def test_two_taps_at_once_add_each_item_once(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    await connect(shopper)
    body = {"modality": "PICKUP", "item_ids": ids(trip), "again": False}
    url = f"/api/trips/{trip['id']}/send-to-cart"
    responses = await asyncio.gather(
        *(shopper.post(url, json=body, headers=CSRF) for _ in range(3))
    )
    assert sorted(response.status_code for response in responses) == [200, 409, 409]
    assert len(fake(app).cart) == 4


async def test_only_items_on_the_list_can_go(
    shopper: httpx.AsyncClient, trip: dict[str, Any]
) -> None:
    await connect(shopper)
    body = await send(shopper, trip["id"], ["not-an-item"], status=404)
    assert body["error"]["code"] == "item_not_found"
    missing = await send(shopper, "no-such-trip", ids(trip), status=404)
    assert missing["error"]["code"] == "trip_not_found"


async def test_a_finished_trip_cant_be_sent(
    shopper: httpx.AsyncClient, trip: dict[str, Any]
) -> None:
    await connect(shopper)
    finish = {"op_id": "op-finish-1", "kind": "trip.finish", "client_ts": NOW_MS}
    await shopper.post(
        f"/api/trips/{trip['id']}/ops",
        json={"client_id": "phone-a", "known_version": 0, "ops": [finish]},
        headers=CSRF,
    )
    body = await send(shopper, trip["id"], ids(trip), status=409)
    assert body["error"]["code"] == "trip_finished"


# ---- tidying -----------------------------------------------------------------------------------


async def sends(app: FastAPI) -> int:
    async with app_state(app).db.read() as db:
        return await db.scalar(select(func.count()).select_from(CartSend)) or 0


async def test_sends_are_kept_a_week(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI, clock: FakeClock
) -> None:
    await connect(shopper)
    await send(shopper, trip["id"], ids(trip))
    state = app_state(app)
    clock.advance(days=6)
    async with state.db.write() as tx:
        await cart.prune(tx.session, clock.now())
    assert await sends(app) == 4
    clock.advance(days=1, seconds=1)
    async with state.db.write() as tx:
        await cart.prune(tx.session, clock.now())
    assert await sends(app) == 0


async def test_sends_go_a_day_after_the_trip_is_finished(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI, clock: FakeClock
) -> None:
    await connect(shopper)
    await send(shopper, trip["id"], ids(trip))
    finish = {"op_id": "op-finish-1", "kind": "trip.finish", "client_ts": NOW_MS}
    await shopper.post(
        f"/api/trips/{trip['id']}/ops",
        json={"client_id": "phone-a", "known_version": 0, "ops": [finish]},
        headers=CSRF,
    )
    state = app_state(app)
    clock.advance(hours=23)
    async with state.db.write() as tx:
        await cart.prune(tx.session, clock.now())
    assert await sends(app) == 4
    clock.advance(hours=1, seconds=1)
    async with state.db.write() as tx:
        await cart.prune(tx.session, clock.now())
    assert await sends(app) == 0


async def test_what_is_sent_never_reaches_the_logs(
    shopper: httpx.AsyncClient, trip: dict[str, Any], app: FastAPI
) -> None:
    from structlog.testing import capture_logs

    await connect(shopper)
    with capture_logs() as logs:
        await send(shopper, trip["id"], ids(trip))
    text = repr(logs)
    for upc in (BEEF, SHELLS, CHEDDAR, BEANS):
        assert upc not in text
    summary = [entry for entry in logs if entry["event"] == "cart.sent"]
    assert summary and summary[0]["added"] == 4


def test_cart_items_are_whole_units() -> None:
    assert CartItem("0000000000001", 2, Modality.PICKUP).quantity == 2
