"""Parsing Kroger responses, quirks included (docs/PLAN.md §7.1). All data is synthetic."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

from dinnerbell.kroger.parse import (
    SoldBy,
    dollars_to_cents,
    parse_chains,
    parse_locations,
    parse_product,
    parse_products,
)


def raw_product(**item: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "itemId": "0000000000042",
        "size": "16 oz",
        "soldBy": "UNIT",
        "price": {"regular": Decimal("2.19"), "promo": Decimal("0")},
    }
    body.update(item)
    return {
        "productId": "0000000000042",
        "upc": "0000000000042",
        "description": "Sample Chunky Salsa",
        "brand": "Sample Kitchen",
        "categories": ["International"],
        "items": [body],
        "aisleLocations": [{"number": "9", "side": "L", "description": "INTL", "bayNumber": "5"}],
    }


@pytest.mark.parametrize(
    ("dollars", "cents"),
    [("1.15", 115), ("4.35", 435), ("2.19", 219), ("0.005", 1), ("0", None), ("-1", None)],
)
def test_dollars_become_exact_cents(dollars: str, cents: int | None) -> None:
    assert dollars_to_cents(Decimal(dollars)) == cents
    assert dollars_to_cents(dollars) == cents


def test_a_float_never_becomes_money() -> None:
    with pytest.raises(TypeError):
        dollars_to_cents(2.19)


def test_prices_parsed_from_json_text_are_exact() -> None:
    body = json.loads(
        '{"data": [{"productId": "1", "items": [{"price": {"regular": 1.15, "promo": 0.99}}]}]}',
        parse_float=Decimal,
    )
    (product,) = parse_products(body)
    assert product.price is not None
    assert (product.price.regular, product.price.promo) == (115, 99)


def test_a_promo_of_zero_means_no_promo() -> None:
    product = parse_product(raw_product())
    assert product is not None and product.price is not None
    assert product.price.regular == 219
    assert product.price.promo is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("UNIT", SoldBy.UNIT), ("Unit", SoldBy.UNIT), ("weight", SoldBy.WEIGHT), ("bulk", None)],
)
def test_sold_by_is_read_case_insensitively(value: str, expected: SoldBy | None) -> None:
    product = parse_product(raw_product(soldBy=value))
    assert product is not None
    assert product.sold_by is expected


@pytest.mark.parametrize("key", ["instore", "inStore", "INSTORE"])
def test_fulfillment_keys_in_any_casing(key: str) -> None:
    product = parse_product(raw_product(fulfillment={key: False}))
    assert product is not None
    assert product.in_store is False


def test_placeholder_aisles_are_not_real_aisles() -> None:
    raw = raw_product()
    raw["aisleLocations"] = [{"number": "0", "description": "PRODUCE"}]
    product = parse_product(raw)
    assert product is not None
    assert product.aisles[0].number is None
    assert product.aisles[0].description == "PRODUCE"
    assert product.aisle is None


def test_a_real_aisle_keeps_its_number_side_and_bay() -> None:
    product = parse_product(raw_product())
    assert product is not None and product.aisle is not None
    assert (product.aisle.number, product.aisle.side, product.aisle.bay) == (9, "L", 5)


def test_the_featured_image_wins_and_sizes_follow_preference() -> None:
    raw = raw_product()
    raw["images"] = [
        {"perspective": "back", "sizes": [{"size": "medium", "url": "https://img.test/back"}]},
        {
            "perspective": "front",
            "featured": True,
            "sizes": [
                {"size": "thumbnail", "url": "https://img.test/t"},
                {"size": "large", "url": "https://img.test/l"},
            ],
        },
    ]
    product = parse_product(raw)
    assert product is not None and product.image is not None
    assert product.image.url() == "https://img.test/l"  # no medium: large is next
    assert product.image.url("thumbnail") == "https://img.test/t"


def test_promo_dates_accept_dates_strings_and_value_objects() -> None:
    product = parse_product(
        raw_product(
            price={
                "regular": Decimal("3.29"),
                "promo": Decimal("2.50"),
                "effectiveDate": "2026-10-01",
                "expirationDate": {"value": "2026-10-13T03:59:59Z", "timezone": "UTC"},
            }
        )
    )
    assert product is not None and product.price is not None
    assert product.price.effective == date(2026, 10, 1)
    assert product.price.expires == datetime(2026, 10, 13, 3, 59, 59, tzinfo=UTC)


def test_the_each_estimate_is_kept_as_exact_cents() -> None:
    product = parse_product(
        raw_product(price={"regular": Decimal("2.19"), "regularPerUnitEstimate": Decimal("0.0995")})
    )
    assert product is not None and product.price is not None
    assert product.price.regular_each_estimate == Fraction(199, 20)


def test_missing_pieces_are_none_not_errors() -> None:
    product = parse_product({"productId": "0000000000043"})
    assert product is not None
    assert (product.size, product.price, product.image, product.sold_by) == (None, None, None, None)
    assert parse_product({"description": "no id"}) is None
    assert parse_products({"data": {"productId": "7"}})[0].product_id == "7"
    assert parse_products({"unexpected": True}) == ()


def test_locations_flag_fuel_centers_and_read_the_time_zone() -> None:
    body = {
        "data": [
            {
                "locationId": "99999001",
                "chain": "SAMPLE MARKET",
                "name": "Sample Market Downtown",
                "address": {"addressLine1": "100 Sample Street", "city": "Sampleton"},
                "hours": {"timezone": "America/New_York", "Open24": False},
                "departments": [{"name": "Produce"}, {"departmentId": "x"}],
            },
            {"locationId": "99999901", "chain": "Shell Company", "name": "Sample Fuel"},
            {"name": "no id"},
        ]
    }
    store, fuel = parse_locations(body)
    assert (store.is_fuel_center, fuel.is_fuel_center) == (False, True)
    assert store.timezone == "America/New_York"
    assert store.departments == ("Produce",)
    assert store.address_line1 == "100 Sample Street"


def test_chains_may_lack_a_domain() -> None:
    chains = parse_chains(
        {"data": [{"name": "SAMPLE MARKET", "domain": "example.com"}, {"name": "OTHER"}]}
    )
    assert [(chain.name, chain.domain) for chain in chains] == [
        ("SAMPLE MARKET", "example.com"),
        ("OTHER", None),
    ]
