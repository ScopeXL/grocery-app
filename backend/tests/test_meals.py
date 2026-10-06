"""Mains and Sides, their lines and costs, and household photos (synthetic data only)."""

from __future__ import annotations

import io
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image

from dinnerbell.core.clock import FakeClock
from dinnerbell.meals.service import purge_orphan_photos
from dinnerbell.state import AppState
from tests.support import CSRF, login

CHEDDAR = "0000000000002"  # "8 oz bag", $2.50
BEEF = "0000000000003"  # "1 lb", sold by unit, $5.49 (promo $4.99 until Oct 10)
TORTILLAS = "0000000000005"  # "10 ct", $2.29
LIME = "0000000000019"  # "1 each", $0.33, no photo


@pytest.fixture
async def cook(client: httpx.AsyncClient) -> httpx.AsyncClient:
    await login(client)
    await client.put("/api/stores/active", json={"location_id": "99999001"}, headers=CSRF)
    return client


async def item(client: httpx.AsyncClient, name: str, product_id: str | None = None) -> str:
    body: dict[str, Any] = {"name": name} | ({"product_id": product_id} if product_id else {})
    return (await client.post("/api/items", json=body, headers=CSRF)).json()["id"]


def line(item_id: str, kind: str, value: str, unit: str | None = None) -> dict[str, Any]:
    return {"item_id": item_id, "amount": {"kind": kind, "value": value, "unit": unit}}


async def tacos(client: httpx.AsyncClient, **extra: Any) -> dict[str, Any]:
    cheddar = await item(client, "Shredded cheddar", CHEDDAR)
    beef = await item(client, "Ground beef", BEEF)
    tortillas = await item(client, "Tortillas", TORTILLAS)
    candles = await item(client, "Hot sauce")  # not linked: no price
    body = {
        "name": "Tacos",
        "role": "main",
        "lines": [
            line(cheddar, "packages", "1/2"),
            line(beef, "measure", "12", "oz"),
            line(tortillas, "count", "4"),
            line(candles, "packages", "1"),
        ],
    } | extra
    response = await client.post("/api/dishes", json=body, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()


def jpeg(width: int, height: int, *, orientation: int | None = None, gps: bool = False) -> bytes:
    image = Image.new("RGB", (width, height), (200, 120, 60))
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if gps:
        exif[0x010F] = "Sample Camera"
        exif.get_ifd(0x8825)[2] = (39.0, 57.0, 0.0)  # a made-up latitude
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


async def test_a_new_main_with_lines_amounts_and_cost(cook: httpx.AsyncClient) -> None:
    dish = await tacos(cook)
    assert (dish["name"], dish["role"], dish["occasions"]) == ("Tacos", "main", ["dinner"])
    texts = [(ln["item"]["name"], ln["amount"]["text"]) for ln in dish["lines"]]
    assert texts == [
        ("Shredded cheddar", "1/2 bag"),
        ("Ground beef", "12 oz"),
        ("Tortillas", "4"),
        ("Hot sauce", "1 package"),
    ]
    costs = [ln["cost_cents"] for ln in dish["lines"]]
    # 1/2 of $2.50; 3/4 of the $4.99 sale price; 4 of 10 at $2.29; no product, no price.
    assert costs == [125, 374, 92, None]
    assert dish["cost"] == {"about_dollars": 6, "cents": 591, "unpriced": 1}
    assert all(ln["check_amount"] is None for ln in dish["lines"])


async def test_an_amount_that_doesnt_fit_the_item_is_refused_by_name(
    cook: httpx.AsyncClient,
) -> None:
    cheddar = await item(cook, "Shredded cheddar", CHEDDAR)
    response = await cook.post(
        "/api/dishes",
        json={"name": "Odd", "role": "side", "lines": [line(cheddar, "measure", "1", "cup")]},
        headers=CSRF,
    )
    assert response.status_code == 422
    assert response.json()["error"]["message"].startswith("Shredded cheddar: ")


async def test_cards_put_favorites_first_and_show_item_photos(cook: httpx.AsyncClient) -> None:
    taco = await tacos(cook)
    lime = await item(cook, "Lime", LIME)
    rice = await cook.post(
        "/api/dishes",
        json={"name": "Lime rice", "role": "side", "lines": [line(lime, "count", "1")]},
        headers=CSRF,
    )
    await cook.post(
        "/api/dishes", json={"name": "Apple pie", "role": "main", "favorite": True}, headers=CSRF
    )
    mains = (await cook.get("/api/dishes", params={"role": "main"})).json()
    assert [card["name"] for card in mains] == ["Apple pie", "Tacos"]
    taco_card = mains[1]
    assert taco_card["item_images"] == [
        f"/api/kroger/fake-images/{CHEDDAR}.svg",
        f"/api/kroger/fake-images/{BEEF}.svg",
        f"/api/kroger/fake-images/{TORTILLAS}.svg",
    ]
    assert taco_card["cost"]["about_dollars"] == 6
    sides = (await cook.get("/api/dishes", params={"role": "side"})).json()
    assert [(card["name"], card["item_images"]) for card in sides] == [("Lime rice", [])]
    assert rice.json()["cost"]["cents"] == 33
    found = (await cook.get("/api/dishes", params={"q": "TAC"})).json()
    assert [card["id"] for card in found] == [taco["id"]]


async def test_favorite_archive_restore_duplicate(cook: httpx.AsyncClient) -> None:
    taco = await tacos(cook)
    starred = await cook.patch(f"/api/dishes/{taco['id']}", json={"favorite": True}, headers=CSRF)
    assert starred.json()["favorite"] is True
    await cook.post(f"/api/dishes/{taco['id']}/archive", headers=CSRF)
    assert (await cook.get("/api/dishes")).json() == []
    archived = (await cook.get("/api/dishes", params={"archived": True})).json()
    assert [card["name"] for card in archived] == ["Tacos"]
    restored = await cook.post(f"/api/dishes/{taco['id']}/restore", headers=CSRF)
    assert restored.json()["archived"] is False
    copy = await cook.post(f"/api/dishes/{taco['id']}/duplicate", headers=CSRF)
    assert copy.status_code == 201
    assert (copy.json()["name"], copy.json()["favorite"]) == ("Tacos (copy)", False)
    assert [ln["amount"] for ln in copy.json()["lines"]] == [ln["amount"] for ln in taco["lines"]]


async def test_editing_fields_and_replacing_lines(cook: httpx.AsyncClient) -> None:
    taco = await tacos(cook)
    edited = await cook.patch(
        f"/api/dishes/{taco['id']}",
        json={
            "name": "Taco night",
            "occasions": ["dinner", "lunch", "dinner"],
            "servings": 4,
            "notes": "Warm the shells.",
            "recipe_url": "https://example.com/tacos",
        },
        headers=CSRF,
    )
    body = edited.json()
    assert (body["name"], body["occasions"], body["servings"]) == (
        "Taco night",
        ["dinner", "lunch"],
        4,
    )
    lime = await item(cook, "Lime", LIME)
    replaced = await cook.put(
        f"/api/dishes/{taco['id']}/lines", json={"lines": [line(lime, "count", "2")]}, headers=CSRF
    )
    assert [ln["item"]["name"] for ln in replaced.json()["lines"]] == ["Lime"]
    bad_url = await cook.patch(
        f"/api/dishes/{taco['id']}", json={"recipe_url": "javascript:alert(1)"}, headers=CSRF
    )
    assert bad_url.status_code == 422


async def test_a_size_fix_that_breaks_an_amount_asks_for_a_check(cook: httpx.AsyncClient) -> None:
    taco = await tacos(cook)
    beef_id = taco["lines"][1]["item"]["id"]
    await cook.patch(f"/api/items/{beef_id}", json={"size_text": "4 ct"}, headers=CSRF)
    dish = (await cook.get(f"/api/dishes/{taco['id']}")).json()
    beef = dish["lines"][1]
    assert beef["check_amount"]  # 12 oz of a 4-count pack can't be worked out
    assert beef["cost_cents"] is None
    assert dish["cost"]["unpriced"] == 2


async def test_photos_are_upright_resized_webp_without_metadata(cook: httpx.AsyncClient) -> None:
    upload = await cook.post(
        "/api/photos",
        content=jpeg(3200, 1600, orientation=6, gps=True),
        headers=CSRF | {"content-type": "image/jpeg"},
    )
    assert upload.status_code == 201, upload.text
    photo = upload.json()
    assert (photo["width"], photo["height"]) == (800, 1600)  # rotated upright, then fit to 1600
    full = await cook.get(f"/api/photos/{photo['id']}")
    assert full.headers["content-type"] == "image/webp"
    assert "immutable" in full.headers["cache-control"]
    with Image.open(io.BytesIO(full.content)) as stored:
        assert stored.format == "WEBP"
        assert stored.size == (800, 1600)
        assert not stored.getexif()
        assert "exif" not in stored.info
    thumb = await cook.get(f"/api/photos/{photo['id']}/thumb")
    with Image.open(io.BytesIO(thumb.content)) as small:
        assert max(small.size) == 400
    dish = await tacos(cook, photo_id=photo["id"])
    assert dish["photo_url"] == f"/api/photos/{photo['id']}"
    card = (await cook.get("/api/dishes")).json()[0]
    assert card["photo_url"] == f"/api/photos/{photo['id']}/thumb"


async def test_uploads_that_arent_photos_are_refused(cook: httpx.AsyncClient) -> None:
    not_image = await cook.post(
        "/api/photos", content=b"hello", headers=CSRF | {"content-type": "text/plain"}
    )
    assert not_image.status_code == 415
    broken = await cook.post(
        "/api/photos", content=b"not really a jpeg", headers=CSRF | {"content-type": "image/jpeg"}
    )
    assert broken.status_code == 422
    assert broken.json()["error"]["code"] == "photo_unreadable"


async def test_unused_photos_are_cleared_after_a_week(
    app: FastAPI, cook: httpx.AsyncClient, clock: FakeClock
) -> None:
    kept = (
        await cook.post(
            "/api/photos", content=jpeg(200, 200), headers=CSRF | {"content-type": "image/jpeg"}
        )
    ).json()
    unused = (
        await cook.post(
            "/api/photos", content=jpeg(200, 200), headers=CSRF | {"content-type": "image/jpeg"}
        )
    ).json()
    await tacos(cook, photo_id=kept["id"])
    state: AppState = app.state.dinnerbell
    async with state.db.write() as tx:
        assert await purge_orphan_photos(tx.session, clock.now() + timedelta(days=6)) == 0
    async with state.db.write() as tx:
        assert await purge_orphan_photos(tx.session, clock.now() + timedelta(days=8)) == 1
    assert (await cook.get(f"/api/photos/{unused['id']}")).status_code == 404
    assert (await cook.get(f"/api/photos/{kept['id']}")).status_code == 200
