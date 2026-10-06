"""Product search, items and the amount picker, against the fake Kroger (synthetic data)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.support import CSRF, login

CHEDDAR = "0000000000002"  # "8 oz bag", $2.50, no promo
SALSA = "0000000000008"  # "16 oz", $3.29, $2.50 Oct 1-14 (date-only)
ONION = "0000000000004"  # sold by weight, $1.49/lb, each estimate $0.75
GREENS = "0000000000016"  # size "Varies"


@pytest.fixture
async def shopper(client: httpx.AsyncClient) -> httpx.AsyncClient:
    await login(client)
    response = await client.put(
        "/api/stores/active", json={"location_id": "99999001"}, headers=CSRF
    )
    assert response.status_code == 200
    return client


async def new_item(client: httpx.AsyncClient, name: str, product_id: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {"name": name}
    if product_id:
        body["product_id"] = product_id
    response = await client.post("/api/items", json=body, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()


async def preview(
    client: httpx.AsyncClient, item_id: str, kind: str, value: Any, unit: str | None = None
) -> httpx.Response:
    amount = {"kind": kind, "value": value, "unit": unit}
    return await client.post(f"/api/items/{item_id}/preview", json={"amount": amount}, headers=CSRF)


async def test_search_needs_a_store_and_three_letters(client: httpx.AsyncClient) -> None:
    await login(client)
    response = await client.get("/api/kroger/products", params={"q": "cheese"})
    assert (response.status_code, response.json()["error"]["code"]) == (409, "store_required")
    await client.put("/api/stores/active", json={"location_id": "99999001"}, headers=CSRF)
    response = await client.get("/api/kroger/products", params={"q": " ch "})
    assert response.json()["error"]["message"] == "Type at least 3 letters."


async def test_search_shows_prices_sales_and_availability(shopper: httpx.AsyncClient) -> None:
    by_id = {
        p["product_id"]: p
        for term in ("cheese", "salsa", "milk", "sour cream")
        for p in (await shopper.get("/api/kroger/products", params={"q": term})).json()
    }
    cheddar = by_id[CHEDDAR]
    assert cheddar["description"] == "Sample Shredded Cheddar Cheese"
    assert cheddar["size"] == "8 oz bag"
    assert cheddar["price"] == {
        "regular_cents": 250,
        "sale_cents": None,
        "sale_ends": None,
        "per_pound": False,
    }
    assert cheddar["image_url"] == f"/api/kroger/fake-images/{CHEDDAR}.svg"
    # A date-only sale end lasts through that day; an instant becomes the local day it falls in.
    assert by_id[SALSA]["price"]["sale_cents"] == 250
    assert by_id[SALSA]["price"]["sale_ends"] == "2026-10-14"
    assert by_id["0000000000001"]["price"]["sale_ends"] == "2026-10-12"
    gouda = by_id["0000000000018"]
    assert (gouda["price"], gouda["availability"]) == (None, "not_sold")
    assert by_id["0000000000017"]["availability"] == "low"


async def test_a_used_up_daily_limit_is_a_quiet_message(shopper: httpx.AsyncClient) -> None:
    response = await shopper.get("/api/kroger/products", params={"q": "dailylimit"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "kroger_daily_limit"
    assert "your list still works" in response.json()["error"]["message"]


async def test_linking_records_the_size_and_how_it_is_sold(shopper: httpx.AsyncClient) -> None:
    cheddar = await new_item(shopper, "Shredded cheddar", CHEDDAR)
    assert cheddar | {"id": "x"} == {
        "id": "x",
        "name": "Shredded cheddar",
        "product_id": CHEDDAR,
        "image_url": f"/api/kroger/fake-images/{CHEDDAR}.svg",
        "size_text": "8 oz bag",
        "size_source": "parsed",
        "sold_by": "unit",
        "each_weight_lb": None,
        "is_staple": False,
        "archived": False,
    }
    candles = await new_item(shopper, "Birthday candles", None)
    assert (candles["product_id"], candles["size_text"], candles["sold_by"]) == (None, None, None)
    names = [i["name"] for i in (await shopper.get("/api/items", params={"q": "CHED"})).json()]
    assert names == ["Shredded cheddar"]


async def test_linking_an_unknown_product_says_to_search_again(shopper: httpx.AsyncClient) -> None:
    response = await shopper.post(
        "/api/items", json={"name": "Mystery", "product_id": "0000000009999"}, headers=CSRF
    )
    assert response.status_code == 404
    assert response.json()["error"]["message"].endswith("Search again.")


async def test_the_picker_and_its_live_preview(shopper: httpx.AsyncClient) -> None:
    cheddar = await new_item(shopper, "Shredded cheddar", CHEDDAR)
    picker = (await shopper.get(f"/api/items/{cheddar['id']}/picker")).json()
    kinds = {kind["kind"]: kind for kind in picker["kinds"]}
    assert "packages" in kinds and "measure" in kinds
    assert "oz" in kinds["measure"]["units"]
    assert not picker["fix_size"]
    assert picker["product"]["description"] == "Sample Shredded Cheddar Cheese"

    half = await preview(shopper, cheddar["id"], "packages", "1/2")
    assert half.json() == {
        "valid": True,
        "message": None,
        "amount": {"kind": "packages", "value": "1/2", "unit": None, "text": "1/2 bag"},
        "share_text": "About half the 8 oz bag",
        "cost_cents": 125,
    }
    cup = (await preview(shopper, cheddar["id"], "measure", "1", "cup")).json()
    assert cup["valid"] is False and cup["message"]


async def test_amounts_must_be_text_never_floats(shopper: httpx.AsyncClient) -> None:
    cheddar = await new_item(shopper, "Shredded cheddar", CHEDDAR)
    assert (await preview(shopper, cheddar["id"], "packages", 0.5)).status_code == 422
    words = (await preview(shopper, cheddar["id"], "packages", "half")).json()
    assert words["valid"] is False


async def test_fix_size_for_a_size_kroger_cant_state(shopper: httpx.AsyncClient) -> None:
    greens = await new_item(shopper, "Spring mix", GREENS)
    assert greens["size_text"] is None
    assert (await shopper.get(f"/api/items/{greens['id']}/picker")).json()["fix_size"] is True
    bad = await shopper.patch(
        f"/api/items/{greens['id']}", json={"size_text": "lots"}, headers=CSRF
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "size_unreadable"
    fixed = await shopper.patch(
        f"/api/items/{greens['id']}", json={"size_text": "5 OZ"}, headers=CSRF
    )
    assert (fixed.json()["size_text"], fixed.json()["size_source"]) == ("5 oz", "household")
    assert (await shopper.get(f"/api/items/{greens['id']}/picker")).json()["fix_size"] is False
    undone = await shopper.patch(
        f"/api/items/{greens['id']}", json={"size_text": None}, headers=CSRF
    )
    assert (undone.json()["size_text"], undone.json()["size_source"]) == (None, "parsed")


async def test_each_weight_for_produce_sold_by_the_pound(shopper: httpx.AsyncClient) -> None:
    onion = await new_item(shopper, "Yellow onion", ONION)
    assert onion["sold_by"] == "weight"
    picker = (await shopper.get(f"/api/items/{onion['id']}/picker")).json()
    assert {kind["kind"] for kind in picker["kinds"]} >= {"measure", "count"}
    assert picker["each_weight"] is not None
    bad = await shopper.patch(
        f"/api/items/{onion['id']}", json={"each_weight_lb": "0"}, headers=CSRF
    )
    assert bad.status_code == 422
    set_ = await shopper.patch(
        f"/api/items/{onion['id']}", json={"each_weight_lb": "1/2"}, headers=CSRF
    )
    assert set_.json()["each_weight_lb"] == "1/2"
    three = (await preview(shopper, onion["id"], "count", "3")).json()
    assert three["valid"] is True
    assert three["cost_cents"] == 224  # 1.5 lb at $1.49 (PLAN §8.5 W3)


async def test_archive_and_restore_an_item(shopper: httpx.AsyncClient) -> None:
    item = await new_item(shopper, "Shredded cheddar", CHEDDAR)
    archived = await shopper.post(f"/api/items/{item['id']}/archive", headers=CSRF)
    assert archived.json()["archived"] is True
    assert (await shopper.get("/api/items")).json() == []
    await shopper.post(f"/api/items/{item['id']}/restore", headers=CSRF)
    assert [i["id"] for i in (await shopper.get("/api/items")).json()] == [item["id"]]
