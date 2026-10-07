"""This week's plan and its shopping list, through the API (synthetic data only).

The fake store's prices (kroger/fixtures/products.json) on 2026-10-06:
beef "1 lb" $5.49 (sale $4.99 through Oct 10), taco shells "12 ct" $2.29, cheddar "8 oz bag"
$2.50, black beans "15 oz can" $1.09, onions sold by the pound at $1.49, milk "1 gal" $3.49
(sale $2.99), olive oil "16.9 fl oz" $8.99, salsa "16 oz" $3.29 (sale $2.50 through Oct 14).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from dinnerbell.kroger.client import KrogerUnavailableError
from dinnerbell.state import AppState
from tests.support import CSRF, login
from tests.test_meals import item, line

BEEF = "0000000000003"
SHELLS = "0000000000006"
CHEDDAR = "0000000000002"
BEANS = "0000000000010"
ONION = "0000000000004"
MILK = "0000000000001"
OIL = "0000000000013"
SALSA = "0000000000008"
RICE = "0000000000007"


@pytest.fixture
async def cook(client: httpx.AsyncClient) -> httpx.AsyncClient:
    await login(client)
    await client.put("/api/stores/active", json={"location_id": "99999001"}, headers=CSRF)
    member = (
        await client.post("/api/members", json={"name": "Sample Parent"}, headers=CSRF)
    ).json()
    await client.put("/api/auth/member", json={"member_id": member["id"]}, headers=CSRF)
    return client


async def dish(client: httpx.AsyncClient, name: str, role: str, lines: list[Any]) -> str:
    response = await client.post(
        "/api/dishes", json={"name": name, "role": role, "lines": lines}, headers=CSRF
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def plan_meal(client: httpx.AsyncClient, main_id: str, **body: Any) -> dict[str, Any]:
    response = await client.post("/api/plan/meals", json={"main_id": main_id} | body, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()


async def taco_night(client: httpx.AsyncClient) -> dict[str, str]:
    """Tacos and Chili share ground beef; Rice is a side."""
    ids = {
        "beef": await item(client, "Ground beef", BEEF),
        "shells": await item(client, "Taco shells", SHELLS),
        "cheddar": await item(client, "Shredded cheddar", CHEDDAR),
        "beans": await item(client, "Black beans", BEANS),
        "onion": await item(client, "Yellow onion", ONION),
        "rice": await item(client, "Rice", RICE),
    }
    ids["tacos"] = await dish(
        client,
        "Tacos",
        "main",
        [
            line(ids["beef"], "measure", "1", "lb"),
            line(ids["shells"], "count", "6"),
            line(ids["cheddar"], "packages", "1/2"),
        ],
    )
    ids["chili"] = await dish(
        client,
        "Chili",
        "main",
        [
            line(ids["beef"], "packages", "1/2"),
            line(ids["beans"], "packages", "2"),
            line(ids["onion"], "measure", "8", "oz"),
        ],
    )
    ids["rice_side"] = await dish(client, "Rice", "side", [line(ids["rice"], "packages", "1/4")])
    return ids


def by_name(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {ln["name"]: ln for ln in plan["lines"]}


# ---- the acceptance case ------------------------------------------------------------------------


async def test_tacos_twice_and_chili_merge_round_and_add_up(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    await plan_meal(cook, ids["tacos"], scale="2")
    plan = await plan_meal(cook, ids["chili"])
    lines = by_name(plan)
    # Beef: 2 x 1 lb for Tacos plus 1/2 package for Chili = 2 1/2 -> 3 packages at $4.99.
    beef = lines["Ground beef"]
    assert (beef["quantity"], beef["quantity_text"], beef["cost_cents"]) == (
        "3",
        "3 packages",
        1497,
    )
    assert beef["regular_cents"] == 1647
    assert beef["sale"] == {"savings_cents": 150, "ends": "2026-10-10"}
    assert [use["name"] for use in beef["used_by"]] == ["Tacos", "Chili"]
    # 12 of the 12 shells; 2 halves of cheddar make 1 bag; 2 cans; 8 oz of onion is 1/2 lb.
    assert (lines["Taco shells"]["quantity"], lines["Taco shells"]["cost_cents"]) == ("1", 229)
    assert (lines["Shredded cheddar"]["quantity"], lines["Shredded cheddar"]["cost_cents"]) == (
        "1",
        250,
    )
    assert (lines["Black beans"]["quantity_text"], lines["Black beans"]["cost_cents"]) == (
        "2 cans",
        218,
    )
    onion = lines["Yellow onion"]
    assert (onion["unit"], onion["quantity"], onion["quantity_text"]) == ("pound", "1/2", "1/2 lb")
    assert onion["cost_cents"] == 75  # half of $1.49, rounded half up
    totals = plan["totals"]
    assert totals["total_cents"] == 1497 + 229 + 250 + 218 + 75 == 2269
    assert (totals["savings_cents"], totals["regular_total_cents"]) == (150, 2419)
    assert (totals["total_text"], totals["savings_text"]) == ("About $23", "$1.50 off on sale")
    assert totals["prices_as_of_text"] == "Prices as of 10:00 AM"
    assert totals["not_priced"] == 0 and totals["not_priced_text"] is None


async def test_lines_follow_the_walk_through_the_store(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    await plan_meal(cook, ids["tacos"])
    plan = await plan_meal(cook, ids["chili"])
    sections = [(ln["name"], ln["section"]["label"]) for ln in plan["lines"]]
    # Produce first, then aisles in number order, meat near the end (PLAN §7.3).
    assert sections == [
        ("Yellow onion", "Produce"),
        ("Taco shells", "Aisle 9, right side"),
        ("Black beans", "Aisle 10, left side"),
        ("Shredded cheddar", "Aisle 21, right side"),
        ("Ground beef", "Meat & Seafood"),
    ]


async def test_an_empty_plan(cook: httpx.AsyncClient) -> None:
    plan = (await cook.get("/api/plan")).json()
    assert (plan["id"], plan["meals"], plan["lines"], plan["extras"]) == (None, [], [], [])
    assert plan["today"] == "2026-10-06"
    assert plan["totals"]["total_text"] == "About $0"
    assert plan["totals"]["prices_as_of_text"] is None


# ---- planned meals ------------------------------------------------------------------------------


async def test_a_meal_with_sides_a_day_and_who_added_it(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    plan = await plan_meal(
        cook, ids["tacos"], side_ids=[ids["rice_side"]], day="2026-10-07", occasion="dinner"
    )
    [meal] = plan["meals"]
    assert plan["changed"] == meal["id"]
    assert meal["main"]["name"] == "Tacos"
    assert [side["name"] for side in meal["sides"]] == ["Rice"]
    assert (meal["day"], meal["occasion"], meal["scale"]) == ("2026-10-07", "dinner", "1")
    assert meal["added_by"]["name"] == "Sample Parent"
    assert meal["main"]["item_images"][0].endswith(f"{BEEF}.svg")
    rice = by_name(plan)["Rice"]
    assert [(use["name"], use["dish_names"]) for use in rice["used_by"]] == [("Tacos", ["Rice"])]


async def test_meals_with_a_day_come_first_in_day_order(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    await plan_meal(cook, ids["tacos"])
    await plan_meal(cook, ids["chili"], day="2026-10-09")
    plan = await plan_meal(cook, ids["tacos"], day="2026-10-06")
    assert [(m["main"]["name"], m["day"]) for m in plan["meals"]] == [
        ("Tacos", "2026-10-06"),
        ("Chili", "2026-10-09"),
        ("Tacos", None),
    ]


async def test_change_a_meal_then_remove_it_with_undo(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    meal_id = (await plan_meal(cook, ids["tacos"], day="2026-10-07"))["changed"]
    changed = await cook.patch(
        f"/api/plan/meals/{meal_id}",
        json={"main_id": ids["chili"], "day": None, "scale": "1/2", "occasion": "lunch"},
        headers=CSRF,
    )
    meal = changed.json()["meals"][0]
    assert (meal["main"]["name"], meal["day"], meal["scale"], meal["occasion"]) == (
        "Chili",
        None,
        "1/2",
        "lunch",
    )
    sides = await cook.put(
        f"/api/plan/meals/{meal_id}/sides", json={"side_ids": [ids["rice_side"]]}, headers=CSRF
    )
    assert [s["name"] for s in sides.json()["meals"][0]["sides"]] == ["Rice"]

    removed = await cook.delete(f"/api/plan/meals/{meal_id}", headers=CSRF)
    assert removed.json()["meals"] == [] and removed.json()["lines"] == []
    restored = await cook.post(f"/api/plan/meals/{meal_id}/restore", headers=CSRF)
    assert [m["id"] for m in restored.json()["meals"]] == [meal_id]


async def test_only_mains_and_sides_in_their_places(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    wrong = await cook.post("/api/plan/meals", json={"main_id": ids["rice_side"]}, headers=CSRF)
    assert (wrong.status_code, wrong.json()["error"]["message"]) == (422, "Choose a Main here.")
    wrong = await cook.post(
        "/api/plan/meals",
        json={"main_id": ids["tacos"], "side_ids": [ids["chili"]]},
        headers=CSRF,
    )
    assert (wrong.status_code, wrong.json()["error"]["message"]) == (422, "Choose a Side here.")
    gone = await cook.patch("/api/plan/meals/nope", json={"scale": "2"}, headers=CSRF)
    assert gone.status_code == 404


# ---- usual sides --------------------------------------------------------------------------------


async def test_usual_sides_are_learned_and_can_be_edited(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    beans_side = await dish(cook, "Refried beans", "side", [])
    salad = await dish(cook, "Side salad", "side", [])
    url = f"/api/dishes/{ids['tacos']}/usual-sides"
    assert (await cook.get(url)).json() == []

    await plan_meal(cook, ids["tacos"], side_ids=[ids["rice_side"], beans_side])
    await plan_meal(cook, ids["tacos"], side_ids=[beans_side])
    learned = (await cook.get(url)).json()
    assert [(s["name"], s["pinned"]) for s in learned] == [
        ("Refried beans", False),  # chosen twice
        ("Rice", False),
    ]

    edited = await cook.put(url, json={"side_ids": [salad, ids["rice_side"]]}, headers=CSRF)
    assert [(s["name"], s["pinned"]) for s in edited.json()] == [
        ("Rice", True),
        ("Side salad", True),
    ]
    # Refried beans stays hidden however often it's chosen again.
    await plan_meal(cook, ids["tacos"], side_ids=[beans_side])
    assert [s["name"] for s in (await cook.get(url)).json()] == ["Rice", "Side salad"]


# ---- extras -------------------------------------------------------------------------------------


async def test_extras_add_to_lines_or_stand_alone(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    milk = await item(cook, "Milk", MILK)
    await plan_meal(cook, ids["chili"])
    # One more package of beef on top of Chili's half (L5): 2 to buy, still 1/2 left over.
    added = await cook.post(
        "/api/plan/extras", json={"item_id": ids["beef"], "quantity": "1"}, headers=CSRF
    )
    assert added.status_code == 201
    beef = by_name(added.json())["Ground beef"]
    assert (beef["quantity"], beef["computed"], beef["extra"]) == ("2", "2", "1")
    assert [e["added_by"]["name"] for e in beef["extras"]] == ["Sample Parent"]

    await cook.post("/api/plan/extras", json={"item_id": milk}, headers=CSRF)
    again = await cook.post("/api/plan/extras", json={"item_id": milk}, headers=CSRF)
    plan = (
        await cook.post("/api/plan/extras", json={"text": "Birthday candles"}, headers=CSRF)
    ).json()
    milk_line = by_name(plan)["Milk"]
    assert (milk_line["quantity"], milk_line["used_by"]) == ("2", [])  # added twice: 2 gallons
    assert milk_line["cost_cents"] == 2 * 299
    candles = by_name(plan)["Birthday candles"]
    assert (candles["key"].startswith("extra:"), candles["item_id"], candles["cost_cents"]) == (
        True,
        None,
        None,
    )
    assert candles["warnings"] == ["No price"]
    assert plan["totals"]["not_priced"] == 1
    assert [e["name"] for e in plan["extras"]] == ["Ground beef", "Milk", "Birthday candles"]
    assert again.json()["changed"] == plan["extras"][1]["id"]  # the same extra, now 2
    assert plan["extras"][1]["quantity_text"] == "2 packages"


async def test_removed_extras_come_back_as_usuals(cook: httpx.AsyncClient) -> None:
    milk = await item(cook, "Milk", MILK)
    extra_id = (await cook.post("/api/plan/extras", json={"item_id": milk}, headers=CSRF)).json()[
        "changed"
    ]
    plan = (await cook.delete(f"/api/plan/extras/{extra_id}", headers=CSRF)).json()
    assert plan["extras"] == [] and plan["lines"] == []
    assert [(u["name"], u["item_id"]) for u in plan["usuals"]] == [("Milk", milk)]
    restored = (await cook.post(f"/api/plan/extras/{extra_id}/restore", headers=CSRF)).json()
    assert [e["id"] for e in restored["extras"]] == [extra_id]
    assert restored["usuals"] == []  # it's on the list again


async def test_an_extra_needs_an_item_or_text(cook: httpx.AsyncClient) -> None:
    neither = await cook.post("/api/plan/extras", json={"quantity": "1"}, headers=CSRF)
    assert neither.status_code == 422
    too_many = await cook.post(
        "/api/plan/extras", json={"text": "Candles", "quantity": "500"}, headers=CSRF
    )
    assert too_many.status_code == 422


# ---- have it, quantities and swaps --------------------------------------------------------------


async def test_have_it_leaves_the_total_and_an_extra_brings_it_back(
    cook: httpx.AsyncClient,
) -> None:
    ids = await taco_night(cook)
    await cook.patch(f"/api/items/{ids['cheddar']}", json={"is_staple": True}, headers=CSRF)
    plan = await plan_meal(cook, ids["tacos"])
    cheddar = by_name(plan)["Shredded cheddar"]
    assert (cheddar["staple"], cheddar["have_it"]) == (True, None)  # waits in the pantry check
    before = plan["totals"]["total_cents"]

    had = await cook.put(f"/api/plan/items/{ids['cheddar']}", json={"have_it": True}, headers=CSRF)
    cheddar = by_name(had.json())["Shredded cheddar"]
    assert (cheddar["have_it"], cheddar["cost_cents"]) == (True, None)
    assert had.json()["totals"]["total_cents"] == before - 250
    assert had.json()["totals"]["have_it"] == 1

    extra = await cook.post("/api/plan/extras", json={"item_id": ids["cheddar"]}, headers=CSRF)
    assert by_name(extra.json())["Shredded cheddar"]["have_it"] is False


async def test_a_typed_quantity_rides_on_top_of_later_meals(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    await plan_meal(cook, ids["chili"])  # beef: 1/2 package -> 1
    url = f"/api/plan/items/{ids['beef']}"
    typed = await cook.put(url, json={"quantity": "3", "unit": "package"}, headers=CSRF)
    beef = by_name(typed.json())["Ground beef"]
    assert (beef["quantity"], beef["computed"]) == ("3", "1")
    assert "overridden" in beef["flags"]
    # Tacos adds 1 lb: the plan computes 2 now, and the household's +2 still applies (L6).
    later = by_name(await plan_meal(cook, ids["tacos"]))["Ground beef"]
    assert (later["computed"], later["quantity"]) == ("2", "4")

    wrong_unit = await cook.put(url, json={"quantity": "3", "unit": "pound"}, headers=CSRF)
    assert wrong_unit.status_code == 409
    half = await cook.put(url, json={"quantity": "1/2", "unit": "package"}, headers=CSRF)
    assert half.status_code == 422
    reset = await cook.put(url, json={"quantity": None}, headers=CSRF)
    assert by_name(reset.json())["Ground beef"]["quantity"] == "2"


async def test_swap_for_this_trip_or_for_good(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    await plan_meal(cook, ids["chili"])
    url = f"/api/plan/items/{ids['beans']}"
    alternatives = (await cook.get(f"{url}/alternatives")).json()["alternatives"]
    current = [a for a in alternatives if a["current"]]
    assert [a["product"]["product_id"] for a in current] == [BEANS]
    assert current[0]["unit_price_text"] == "$0.073 per oz"  # $1.09 for 15 oz

    swapped = await cook.put(url, json={"swap_product_id": SALSA}, headers=CSRF)
    beans = by_name(swapped.json())["Black beans"]
    assert beans["swapped"] and "swapped" in beans["flags"]
    assert beans["image_url"].endswith(f"{SALSA}.svg")
    assert beans["cost_cents"] == 2 * 250  # 2 packages of the 16 oz salsa, on sale
    item_now = (await cook.get("/api/items")).json()
    assert next(i for i in item_now if i["id"] == ids["beans"])["product_id"] == BEANS

    undone = await cook.put(url, json={"swap_product_id": None}, headers=CSRF)
    assert by_name(undone.json())["Black beans"]["swapped"] is False

    for_good = await cook.put(url, json={"swap_product_id": SALSA, "always": True}, headers=CSRF)
    assert by_name(for_good.json())["Black beans"]["swapped"] is False
    item_now = (await cook.get("/api/items")).json()
    assert next(i for i in item_now if i["id"] == ids["beans"])["product_id"] == SALSA


# ---- prices and weeks ---------------------------------------------------------------------------


async def test_the_list_still_works_when_kroger_does_not_answer(
    cook: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, app: FastAPI
) -> None:
    state: AppState = app.state.dinnerbell
    ids = await taco_night(cook)
    await plan_meal(cook, ids["chili"])

    async def down(*args: object, **kwargs: object) -> object:
        raise KrogerUnavailableError("synthetic outage")

    monkeypatch.setattr(state.catalog, "products", down)
    plan = (await cook.get("/api/plan")).json()
    assert plan["prices_note"] == "Kroger isn't answering right now. Try again in a minute."
    beef = by_name(plan)["Ground beef"]
    assert (beef["quantity"], beef["cost_cents"], beef["warnings"]) == ("1", None, [])
    assert plan["totals"]["not_priced"] == 3


async def test_a_new_week_starts_empty_and_can_be_undone(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    milk = await item(cook, "Milk", MILK)
    first = await plan_meal(cook, ids["tacos"])
    await cook.post("/api/plan/extras", json={"item_id": milk}, headers=CSRF)
    fresh = (await cook.post("/api/plan/new-week", headers=CSRF)).json()
    assert (fresh["id"], fresh["meals"], fresh["changed"]) == (None, [], first["id"])
    assert [u["name"] for u in fresh["usuals"]] == ["Milk"]

    back = (
        await cook.post("/api/plan/new-week/undo", json={"plan_id": first["id"]}, headers=CSRF)
    ).json()
    assert back["id"] == first["id"] and len(back["meals"]) == 1

    await cook.post("/api/plan/new-week", headers=CSRF)
    await plan_meal(cook, ids["chili"])
    refused = await cook.post(
        "/api/plan/new-week/undo", json={"plan_id": first["id"]}, headers=CSRF
    )
    assert refused.status_code == 409


async def test_extras_come_in_whole_packages_or_quarter_pounds(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)

    async def extra(item_id: str, quantity: str) -> httpx.Response:
        body = {"item_id": item_id, "quantity": quantity}
        return await cook.post("/api/plan/extras", json=body, headers=CSRF)

    half = await extra(ids["beef"], "1/2")
    assert (half.status_code, half.json()["error"]["message"]) == (422, "Choose a whole number.")
    third = await extra(ids["onion"], "1/3")  # onions are sold by the pound
    assert third.json()["error"]["message"] == "Choose pounds in quarters, like 1 1/4."
    quarter = await extra(ids["onion"], "5/4")
    assert by_name(quarter.json())["Yellow onion"]["quantity"] == "5/4"

    await plan_meal(cook, ids["chili"])
    typed = await cook.put(
        f"/api/plan/items/{ids['onion']}", json={"quantity": "1/3", "unit": "pound"}, headers=CSRF
    )
    assert typed.status_code == 422


async def test_two_items_for_one_product_are_flagged_not_merged(cook: httpx.AsyncClient) -> None:
    milk = await item(cook, "Milk", MILK)
    whole = await item(cook, "Whole milk", MILK)
    await cook.post("/api/plan/extras", json={"item_id": milk}, headers=CSRF)
    plan = (await cook.post("/api/plan/extras", json={"item_id": whole}, headers=CSRF)).json()
    lines = by_name(plan)
    assert lines["Milk"]["warnings"] == ["Same product as Whole milk"]
    assert lines["Whole milk"]["warnings"] == ["Same product as Milk"]
    assert plan["totals"]["total_cents"] == 2 * 299  # both still count


async def test_each_planned_meal_says_what_it_costs(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    plan = await plan_meal(cook, ids["tacos"], scale="2", side_ids=[ids["rice_side"]])
    [meal] = plan["meals"]
    # Shares, not packages: at x2 Tacos uses 2 lb of beef (2 x $4.99), all 12 shells ($2.29)
    # and the whole cheddar bag ($2.50); Rice x2 uses half the $2.19 bag.
    assert meal["cost"] == {"about_dollars": 16, "cents": 998 + 229 + 250 + 110, "unpriced": 0}


async def test_meal_cards_say_what_is_on_sale(cook: httpx.AsyncClient) -> None:
    ids = await taco_night(cook)
    cards = {c["name"]: c for c in (await cook.get("/api/dishes", params={"role": "main"})).json()}
    assert (cards["Tacos"]["on_sale"], cards["Tacos"]["sale_ends"]) == (True, "2026-10-10")
    assert (cards["Chili"]["on_sale"], cards["Chili"]["sale_ends"]) == (True, "2026-10-10")
    sides = (await cook.get("/api/dishes", params={"role": "side"})).json()
    assert [(c["name"], c["on_sale"]) for c in sides] == [("Rice", False)]
    assert ids  # both mains use the beef on sale
