"""`dinnerbell smoke-kroger` must answer the open questions without printing private values."""

from __future__ import annotations

import io
from typing import Any

import httpx
import pytest

from dinnerbell.kroger import smoke

ZIP = "12345"
STORE_ID = "01234567"
PRODUCT_ID = "0001234567890"
PRIVATE = (
    ZIP,
    STORE_ID,
    PRODUCT_ID,
    "Private Store Name",
    "123 Private Lane",
    "Private Product Name",
    "2.19",
    "219",
    "sample-client-id",
    "sample-client-secret",
    "token-abc",
)
ENV = {
    "KROGER_LIVE": "1",
    "KROGER_CLIENT_ID": "sample-client-id",
    "KROGER_CLIENT_SECRET": "sample-client-secret",
    "KROGER_SMOKE_ZIP": ZIP,
}


def product() -> dict[str, Any]:
    return {
        "productId": PRODUCT_ID,
        "upc": PRODUCT_ID,
        "description": "Private Product Name",
        "images": [
            {
                "perspective": "front",
                "featured": True,
                "sizes": [
                    {
                        "size": "medium",
                        "url": f"https://www.kroger.com/product/images/medium/front/{PRODUCT_ID}",
                    }
                ],
            }
        ],
        "items": [{"size": "1 gal", "soldBy": "UNIT", "price": {"regular": 2.19, "promo": 0}}],
        "aisleLocations": [{"number": "21", "side": "L"}],
    }


def simulated_kroger(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    cache = {"cache-control": "max-age=3600", "x-ratelimit-remaining": "9990"}
    if path.endswith("/connect/oauth2/token"):
        return httpx.Response(200, json={"access_token": "token-abc", "expires_in": 1800})
    if path.endswith("/locations"):
        stores = [
            {"locationId": "99999901", "chain": "SHELL COMPANY", "name": "Fuel"},
            {
                "locationId": STORE_ID,
                "chain": "SAMPLE",
                "name": "Private Store Name",
                "address": {"addressLine1": "123 Private Lane", "zipCode": ZIP},
                "hours": {"timezone": "America/New_York"},
            },
        ]
        return httpx.Response(200, json={"data": stores}, headers=cache)
    if path.endswith("/chains"):
        return httpx.Response(200, json={"data": [{"name": "SAMPLE", "domain": "example.com"}]})
    if path.endswith(f"/products/{PRODUCT_ID}"):
        return httpx.Response(200, json={"data": product()}, headers=cache)
    if path.endswith("/products"):
        return httpx.Response(200, json={"data": [product()]}, headers=cache)
    if "/product/images/" in path:
        return httpx.Response(
            200,
            content=b"\xff\xd8",
            headers={"content-type": "image/jpeg", "access-control-allow-origin": "*"},
        )
    return httpx.Response(404)


async def run(environ: dict[str, str]) -> tuple[int, str]:
    out = io.StringIO()
    code = await smoke.run(environ, out, transport=httpx.MockTransport(simulated_kroger))
    return code, out.getvalue()


async def test_a_full_run_answers_the_questions_and_hides_private_values() -> None:
    code, report = await run(ENV)
    assert code == 0, report
    assert "batch includes store prices: yes (1 of 1 priced)" in report
    assert "image hosts: https://www.kroger.com/product/images/medium/front/<id>" in report
    assert "fuel centers: 1" in report
    assert "x-ratelimit-remaining: 9990" in report
    assert "access-control-allow-origin: *" in report
    assert "'price': {'promo': 'int', 'regular': 'decimal'}" in report  # types, never values
    for value in PRIVATE:
        assert value not in report, f"the report printed a private value: {value}"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"KROGER_LIVE": ""}, "set KROGER_LIVE=1"),
        ({"KROGER_CLIENT_SECRET": ""}, "add KROGER_CLIENT_SECRET"),
        ({"KROGER_SMOKE_ZIP": ""}, "add KROGER_SMOKE_ZIP"),
        ({"KROGER_SMOKE_ZIP": "1234"}, "must be a 5-digit ZIP"),
    ],
)
async def test_it_skips_without_the_opt_in_and_the_local_values(
    changes: dict[str, str], message: str
) -> None:
    code, report = await run(ENV | changes)
    assert code == 0
    assert report.startswith("Skipped") and message in report
    assert "sample-client-secret" not in report
