"""Saved lists and shopping actions (PLAN §9.2, §9.8 "pytest"). Synthetic data only.

Phones stamp actions with corrected time in ms; the fake clock starts at 2026-10-06T14:00Z.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from dinnerbell.core.clock import FakeClock
from dinnerbell.shopping import service as shopping
from dinnerbell.state import AppState
from dinnerbell.stores.models import StoreSection
from tests.support import CSRF, login
from tests.test_meals import item
from tests.test_planning import MILK, by_name, plan_meal, taco_night

NOW_MS = 1791295200000  # 2026-10-06T14:00:00Z


@pytest.fixture
async def shopper(client: httpx.AsyncClient) -> httpx.AsyncClient:
    await login(client)
    await client.put("/api/stores/active", json={"location_id": "99999001"}, headers=CSRF)
    member = (
        await client.post("/api/members", json={"name": "Sample Parent"}, headers=CSRF)
    ).json()
    await client.put("/api/auth/member", json={"member_id": member["id"]}, headers=CSRF)
    return client


@pytest.fixture
def events(app: FastAPI) -> list[tuple[str, dict[str, Any]]]:
    """Every event published after a commit, in order."""
    state: AppState = app.state.dinnerbell
    seen: list[tuple[str, dict[str, Any]]] = []
    original = state.db.publisher

    def record(event_type: str, payload: dict[str, Any]) -> None:
        seen.append((event_type, payload))
        if original is not None:
            original(event_type, payload)

    state.db.publisher = record
    return seen


async def save(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.post("/api/trips", headers=CSRF)
    assert response.status_code in (200, 201), response.text
    return response.json()


def by_item(trip: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in trip["items"]}


def set_state(item_id: str, state: str, ts: int, seq: int = 0, op_id: str = "") -> dict[str, Any]:
    return {
        "op_id": op_id or f"op-{item_id[-8:]}-{ts}-{state}",
        "v": 1,
        "kind": "item.set_state",
        "item_id": item_id,
        "state": state,
        "client_ts": ts,
        "client_seq": seq,
    }


async def send(
    client: httpx.AsyncClient, trip_id: str, *ops: dict[str, Any], known: int = 0
) -> dict[str, Any]:
    body = {"client_id": "phone-a", "known_version": known, "ops": list(ops)}
    response = await client.post(f"/api/trips/{trip_id}/ops", json=body, headers=CSRF)
    assert response.status_code == 200, response.text
    return response.json()


def statuses(result: dict[str, Any]) -> list[str]:
    return [entry["status"] for entry in result["results"]]


# ---- saving ----------------------------------------------------------------------------------


async def test_saving_freezes_the_list_in_walking_order(shopper: httpx.AsyncClient) -> None:
    ids = await taco_night(shopper)
    await plan_meal(shopper, ids["tacos"])
    plan = await plan_meal(shopper, ids["chili"])
    await shopper.put(f"/api/plan/items/{ids['cheddar']}", json={"have_it": True}, headers=CSRF)

    trip = await save(shopper)
    assert trip["status"] == "active" and trip["complete"]
    names = [entry["name"] for entry in trip["items"]]
    planned = [ln["name"] for ln in plan["lines"] if ln["name"] != "Shredded cheddar"]
    assert names == planned  # walking order, without what we have
    beef = by_item(trip)["Ground beef"]
    assert (beef["qty_text"], beef["line_cents"], beef["state"]) == (
        "2 packages, 1 lb each",
        998,
        "todo",
    )
    assert beef["used_by"] == [
        {"meal_id": u["meal_id"], "name": u["name"]}
        for u in by_name(plan)["Ground beef"]["used_by"]
    ]
    assert by_item(trip)["Taco shells"]["section_label"] == "Aisle 9, right side"
    assert trip["estimate_cents"] == plan["totals"]["total_cents"] - 250  # no cheddar
    assert [m["name"] for m in trip["members"]] == ["Sample Parent"]

    view = (await shopper.get("/api/plan")).json()
    assert view["trip"] == {"id": trip["id"], "item_count": 4, "done_count": 0, "stale": False}
    await shopper.patch(
        f"/api/plan/meals/{plan['meals'][0]['id']}", json={"scale": "2"}, headers=CSRF
    )
    assert (await shopper.get("/api/plan")).json()["trip"]["stale"] is True
    # The saved list doesn't move until it's updated (L17).
    again = (await shopper.get(f"/api/trips/{trip['id']}")).json()
    assert by_item(again)["Ground beef"]["quantity"] == "2"


async def test_aisles_on_a_saved_list_join_the_walking_order(
    shopper: httpx.AsyncClient, app: FastAPI
) -> None:
    ids = await taco_night(shopper)
    await plan_meal(shopper, ids["tacos"])
    await plan_meal(shopper, ids["chili"])
    await save(shopper)
    state: AppState = app.state.dinnerbell
    async with state.db.read() as db:
        keys = {s.key: s.sort_index for s in await db.scalars(select(StoreSection))}
    assert (keys["aisle:9"], keys["aisle:10"], keys["aisle:21"]) == (1009, 1010, 1021)


async def test_updating_keeps_what_was_done_and_drops_what_isnt_needed(
    shopper: httpx.AsyncClient,
) -> None:
    ids = await taco_night(shopper)
    tacos = await plan_meal(shopper, ids["tacos"])
    chili = (await plan_meal(shopper, ids["chili"]))["changed"]
    trip = await save(shopper)
    items = by_item(trip)
    await send(
        shopper,
        trip["id"],
        set_state(items["Ground beef"]["id"], "done", NOW_MS),
        set_state(items["Yellow onion"]["id"], "missed", NOW_MS, seq=1),
    )
    milk = await item(shopper, "Milk", MILK)
    await shopper.post("/api/plan/extras", json={"item_id": milk}, headers=CSRF)
    await shopper.delete(f"/api/plan/meals/{chili}", headers=CSRF)

    response = await shopper.post("/api/trips", headers=CSRF)
    assert response.status_code == 200  # the same saved list, brought up to date
    updated = by_item(response.json())
    assert set(updated) == {
        "Ground beef",
        "Taco shells",
        "Shredded cheddar",
        "Yellow onion",
        "Milk",
    }
    assert updated["Ground beef"]["state"] == "done"  # checked off: stays, even if needed less
    assert updated["Ground beef"]["quantity"] == "1"
    assert updated["Yellow onion"]["state"] == "missed"  # couldn't find: stays
    assert updated["Milk"]["state"] == "todo"
    assert response.json()["id"] == trip["id"] and tacos["id"] == trip["plan_id"]
    delta = (
        await shopper.get(f"/api/trips/{trip['id']}", params={"since_version": trip["version"]})
    ).json()
    assert delta["complete"] is False
    assert {e["name"]: e["removed"] for e in delta["items"] if e["removed"]} == {
        "Black beans": True
    }


async def test_nothing_to_save(shopper: httpx.AsyncClient) -> None:
    response = await shopper.post("/api/trips", headers=CSRF)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "nothing_to_save")


# ---- shopping actions ---------------------------------------------------------------------------


async def saved_trip(shopper: httpx.AsyncClient) -> tuple[dict[str, Any], dict[str, str]]:
    ids = await taco_night(shopper)
    await plan_meal(shopper, ids["tacos"])
    trip = await save(shopper)
    return trip, {name: entry["id"] for name, entry in by_item(trip).items()}


async def test_a_resent_action_is_applied_once(shopper: httpx.AsyncClient) -> None:
    trip, items = await saved_trip(shopper)
    action = set_state(items["Ground beef"], "done", NOW_MS, op_id="op-once-0001")
    first = await send(shopper, trip["id"], action)
    second = await send(shopper, trip["id"], action)
    assert statuses(first) == ["applied"]
    assert second["results"] == [
        {"op_id": "op-once-0001", "status": "duplicate", "original": "applied", "reason": None}
    ]
    assert second["trip_version"] == first["trip_version"]


async def test_the_latest_action_wins_per_field(shopper: httpx.AsyncClient) -> None:
    trip, items = await saved_trip(shopper)
    beef = items["Ground beef"]
    # B marked it missed at 17:05; A's offline check-off from 17:00 arrives later and loses.
    later = await send(shopper, trip["id"], set_state(beef, "missed", NOW_MS - 1000))
    older = await send(shopper, trip["id"], set_state(beef, "done", NOW_MS - 5000))
    assert (statuses(later), statuses(older)) == (["applied"], ["superseded"])
    # A tie goes to the later arrival.
    tie = await send(shopper, trip["id"], set_state(beef, "todo", NOW_MS - 1000))
    assert statuses(tie) == ["applied"]
    # A phone whose clock runs fast can't claim the future: it's clamped to arrival.
    fast = await send(shopper, trip["id"], set_state(beef, "done", NOW_MS + 600_000))
    after = await send(shopper, trip["id"], set_state(beef, "missed", NOW_MS))
    assert (statuses(fast), statuses(after)) == (["applied"], ["applied"])
    # The note is its own field: an older note still applies after a newer state.
    note = {
        "op_id": "op-note-0001",
        "kind": "item.set_note",
        "item_id": beef,
        "note": "  Ask at the counter  ",
        "client_ts": NOW_MS - 9000,
    }
    result = await send(shopper, trip["id"], note)
    beef_now = next(e for e in result["items"] if e["id"] == beef)
    assert (beef_now["state"], beef_now["note"]) == ("missed", "Ask at the counter")
    assert beef_now["note_by"] == beef_now["state_by"] is not None


async def test_a_batch_applies_in_order_and_skips_what_it_cant(
    shopper: httpx.AsyncClient,
) -> None:
    trip, items = await saved_trip(shopper)
    shells = items["Taco shells"]
    result = await send(
        shopper,
        trip["id"],
        set_state(shells, "todo", NOW_MS, seq=2),
        set_state(shells, "done", NOW_MS, seq=1),
        set_state("no-such-item", "done", NOW_MS, seq=3),
        {"op_id": "op-odd-00001", "kind": "item.dance", "client_ts": NOW_MS, "client_seq": 4},
        {"op_id": "op-v99-00001", "v": 99, "kind": "trip.finish", "client_ts": NOW_MS},
    )
    by_op = {r["op_id"]: (r["status"], r["reason"]) for r in result["results"]}
    assert by_op["op-odd-00001"] == ("rejected", "unknown_kind")
    assert by_op["op-v99-00001"] == ("rejected", "unknown_version")
    assert ("rejected", "unknown_item") in by_op.values()
    assert next(e for e in result["items"] if e["id"] == shells)["state"] == "todo"  # seq 2 last
    assert result["trip_version"] == trip["version"] + 2  # one version per applied action


async def test_catching_up_by_version(shopper: httpx.AsyncClient) -> None:
    trip, items = await saved_trip(shopper)
    first = await send(shopper, trip["id"], set_state(items["Ground beef"], "done", NOW_MS))
    second = await send(
        shopper,
        trip["id"],
        set_state(items["Taco shells"], "done", NOW_MS),
        known=first["trip_version"],
    )
    assert [e["name"] for e in second["items"]] == ["Taco shells"]
    delta = (
        await shopper.get(f"/api/trips/{trip['id']}", params={"since_version": trip["version"]})
    ).json()
    assert {e["name"] for e in delta["items"]} == {"Ground beef", "Taco shells"}


async def test_finish_reopen_and_late_check_offs(
    shopper: httpx.AsyncClient, clock: FakeClock
) -> None:
    trip, items = await saved_trip(shopper)

    def finish(ts: int, op_id: str, total: int | None = None) -> dict[str, Any]:
        op: dict[str, Any] = {"op_id": op_id, "kind": "trip.finish", "client_ts": ts}
        return op | ({"actual_total_cents": total} if total is not None else {})

    done = await send(shopper, trip["id"], finish(NOW_MS, "op-finish-001"))
    assert (statuses(done), done["trip_status"]) == (["applied"], "finished")
    # Finishing again is superseded, but it can still say what was paid.
    paid = await send(shopper, trip["id"], finish(NOW_MS + 5, "op-finish-002", total=2350))
    assert (statuses(paid), paid["trip"]["actual_total_cents"]) == (["superseded"], 2350)
    # An offline check-off from the store still counts within a day.
    late = await send(shopper, trip["id"], set_state(items["Ground beef"], "done", NOW_MS - 60_000))
    assert (statuses(late), late["trip_status"]) == (["applied"], "finished")
    # A reopen older than the finish loses; a newer one wins.
    old = {"op_id": "op-reopen-001", "kind": "trip.reopen", "client_ts": NOW_MS - 1}
    new = {"op_id": "op-reopen-002", "kind": "trip.reopen", "client_ts": NOW_MS + 10}
    assert statuses(await send(shopper, trip["id"], old)) == ["superseded"]
    reopened = await send(shopper, trip["id"], new)
    assert (statuses(reopened), reopened["trip_status"]) == (["applied"], "active")

    clock.advance(minutes=1)
    await send(shopper, trip["id"], finish(NOW_MS + 60_000, "op-finish-003"))
    clock.advance(hours=25)
    closed = await send(shopper, trip["id"], set_state(items["Taco shells"], "done", NOW_MS))
    assert closed["results"][0]["reason"] == "trip_closed"


async def test_one_event_per_applied_batch(
    shopper: httpx.AsyncClient, events: list[tuple[str, dict[str, Any]]]
) -> None:
    trip, items = await saved_trip(shopper)
    events.clear()
    batch = [
        set_state(items["Ground beef"], "done", NOW_MS, op_id="op-event-001"),
        set_state(items["Taco shells"], "done", NOW_MS, seq=1, op_id="op-event-002"),
    ]
    await send(shopper, trip["id"], *batch)
    assert [kind for kind, _ in events] == ["trip.items"]
    payload = events[0][1]
    assert payload["trip_id"] == trip["id"] and len(payload["items"]) == 2
    assert payload["trip"]["done_count"] == 2
    events.clear()
    await send(shopper, trip["id"], *batch)  # all duplicates
    assert events == []
    await send(
        shopper, trip["id"], {"op_id": "op-fin-0001", "kind": "trip.finish", "client_ts": NOW_MS}
    )
    assert [kind for kind, _ in events] == ["trip.state"]


async def test_batches_too_big_or_broken(shopper: httpx.AsyncClient) -> None:
    trip, _items = await saved_trip(shopper)
    url = f"/api/trips/{trip['id']}/ops"
    huge: dict[str, Any] = {"client_id": "phone-a", "ops": [], "pad": "x" * 70_000}
    assert (await shopper.post(url, json=huge, headers=CSRF)).status_code == 413
    broken = {"client_id": "phone-a", "ops": [{"op_id": "op-broken-01", "kind": "trip.finish"}]}
    assert (await shopper.post(url, json=broken, headers=CSRF)).status_code == 422
    missing = await shopper.post(
        "/api/trips/nope/ops", json={"client_id": "a", "ops": []}, headers=CSRF
    )
    assert missing.status_code == 404


# ---- after the trip ------------------------------------------------------------------------------


async def test_history_shop_again_and_plan_again(shopper: httpx.AsyncClient) -> None:
    trip, items = await saved_trip(shopper)
    await send(
        shopper,
        trip["id"],
        set_state(items["Ground beef"], "done", NOW_MS),
        {
            "op_id": "op-fin-0002",
            "kind": "trip.finish",
            "client_ts": NOW_MS + 1,
            "client_seq": 1,
            "actual_total_cents": 1234,
        },
    )
    history = (await shopper.get("/api/trips")).json()
    assert history["active"] == []
    [finished] = history["finished"]
    assert (finished["actual_total_cents"], finished["done_count"]) == (1234, 1)

    again = await shopper.post(f"/api/trips/{trip['id']}/shop-again", headers=CSRF)
    assert again.status_code == 201
    fresh = again.json()
    assert (fresh["status"], fresh["plan_id"]) == ("active", None)
    assert {e["name"] for e in fresh["items"]} == set(items)
    assert all(e["state"] == "todo" for e in fresh["items"])
    assert by_item(fresh)["Ground beef"]["line_cents"] == 499  # priced today, on sale

    await shopper.post("/api/plan/new-week", headers=CSRF)
    repeated = await shopper.post("/api/plan/repeat", json={"trip_id": trip["id"]}, headers=CSRF)
    assert [m["main"]["name"] for m in repeated.json()["meals"]] == ["Tacos"]


async def test_krogers_copies_are_cleared_a_day_after_the_trip(
    shopper: httpx.AsyncClient, app: FastAPI, clock: FakeClock
) -> None:
    trip, _items = await saved_trip(shopper)
    await send(
        shopper, trip["id"], {"op_id": "op-fin-0003", "kind": "trip.finish", "client_ts": NOW_MS}
    )
    state: AppState = app.state.dinnerbell
    async with state.db.write() as tx:
        assert await shopping.clear_kroger_copies(tx.session, clock.now()) == 0
    async with state.db.write() as tx:
        cleared = await shopping.clear_kroger_copies(tx.session, clock.now() + timedelta(hours=25))
    assert cleared == 1
    after = (await shopper.get(f"/api/trips/{trip['id']}")).json()
    beef = by_item(after)["Ground beef"]
    assert (beef["image_url"], beef["section_label"], beef["aisle_side"]) == (None, None, None)
    assert (beef["qty_text"], beef["line_cents"]) == ("1 package, 1 lb", 499)  # ours, kept


async def test_the_walking_order_can_change_and_lists_follow(
    shopper: httpx.AsyncClient, events: list[tuple[str, dict[str, Any]]]
) -> None:
    trip, _items = await saved_trip(shopper)
    sections = (await shopper.get("/api/stores/active/sections")).json()
    labels = [s["label"] for s in sections]
    assert labels[:3] == ["Produce", "Bakery", "Deli"] and "Aisle 9" in labels
    events.clear()
    backwards = [s["id"] for s in reversed(sections)]
    saved = await shopper.put("/api/stores/active/sections", json={"ids": backwards}, headers=CSRF)
    assert [s["label"] for s in saved.json()] == list(reversed(labels))
    assert "trip.items" in [kind for kind, _ in events]
    after = (await shopper.get(f"/api/trips/{trip['id']}")).json()
    orders = {e["name"]: e["section_order"] for e in after["items"]}
    assert orders["Ground beef"] < orders["Taco shells"]  # meat now comes before aisle 9
    missing = await shopper.put(
        "/api/stores/active/sections", json={"ids": backwards[1:]}, headers=CSRF
    )
    assert missing.status_code == 409
