"""totals.py and the headline: L14 to L16 of PLAN §8.5, and the total's words (§8.4, UX §2)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from dinnerbell.domain.listbuild import build_list
from dinnerbell.domain.models import Flag, Item, Product, SoldBy
from dinnerbell.domain.money import PriceInfo, headline, headline_lines
from dinnerbell.domain.totals import Totals, summarize
from dinnerbell.domain.units import Unit
from tests.domain.builders import (
    NOW,
    by_weight,
    dish,
    line_for,
    meal,
    measure,
    packages,
    plan_input,
    product,
)

MORNING = datetime(2026, 10, 6, 13, 14, tzinfo=UTC)  # 9:14 AM in the household's zone
LATER = datetime(2026, 10, 6, 15, 2, tzinfo=UTC)  # 11:02 AM


def test_l14_the_totals_add_up_priced_lines_only() -> None:
    week = dish(
        "Week",
        ("beans", packages("2")),  # P1: 598 on sale, 698 regular
        ("cheese", measure("6", Unit.OZ)),  # L9: swapped to 2 lb at 899
        ("onions", packages("1/2")),  # L13: swapped to loose at 149/lb, 224
        ("oil", measure("2", Unit.TBSP)),  # have it
        ("salsa", packages("1")),  # no price
    )
    plan = plan_input(
        [meal("meal-1", week)],
        {
            "beans": (
                Item("beans", "Sample Black Beans"),
                product("15 oz can", regular=349, promo=299),
            ),
            "cheese": (Item("cheese", "Sample Shredded Cheddar"), product("8 oz", regular=250)),
            "onions": (Item("onions", "Sample Yellow Onions"), product("3 lb bag")),
            "oil": (Item("oil", "Sample Olive Oil"), product("16.9 fl oz", regular=499)),
            "salsa": (Item("salsa", "Sample Salsa"), product("16 oz", regular=None)),
        },
        have_it={"oil"},
        swaps={
            "cheese": product("2 lb", regular=899, product_id="0000000000002"),
            "onions": by_weight(149, product_id="0000000000003"),
        },
    )
    totals = build_list(plan, NOW).totals
    assert (totals.total, totals.savings, totals.regular_total) == (1721, 100, 1821)
    assert (totals.not_priced, totals.have_it, totals.needs_check) == (1, 1, 0)


def test_l15_the_headline() -> None:
    totals = Totals(14150, 1100, 15250, 3, 0, 0, MORNING)
    assert headline_lines(totals, "9:14 AM") == (
        "About $142",
        "$11 off on sale",
        "Prices as of 9:14 AM",
        "Before tax, fees and tip",
        "3 items have no price",
    )
    assert headline(totals, "9:14 AM") == "\n".join(headline_lines(totals, "9:14 AM"))


def test_l16_prices_are_as_of_the_oldest_priced_line() -> None:
    def fetched(product_id: str, when: datetime) -> Product:
        return Product(product_id, "16 oz", SoldBy.UNIT, PriceInfo(regular=250, fetched_at=when))

    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", packages("1")), ("salsa", packages("1"))))],
        {
            "cheese": (Item("cheese", "Sample Shredded Cheddar"), fetched("0000000000001", LATER)),
            "salsa": (Item("salsa", "Sample Salsa"), fetched("0000000000002", MORNING)),
        },
    )
    assert build_list(plan, NOW).totals.prices_as_of == MORNING


def test_an_at_least_line_counts_its_lower_bound_and_in_the_tally() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", measure("6", Unit.OZ))))],
        {"cheese": (Item("cheese", "Sample Shredded Cheddar"), product("Varies", regular=250))},
    )
    shopping = build_list(plan, NOW)
    assert line_for(shopping, "cheese").at_least
    assert (shopping.totals.total, shopping.totals.not_priced) == (250, 1)


def test_have_it_lines_are_left_out_of_everything_but_their_count() -> None:
    base = build_list(
        plan_input(
            [meal("meal-1", dish("Tacos", ("cheese", packages("1/2"))))],
            {"cheese": (Item("cheese", "Sample Shredded Cheddar"), product("Varies"))},
            swaps={"cheese": product("16 oz", product_id="0000000000002")},
        ),
        NOW,
    ).lines[0]
    with_check = summarize([base])
    assert (with_check.needs_check, with_check.total) == (1, 250)
    had = replace(base, cost_cents=None, regular_cents=None, flags=base.flags | {Flag.HAVE_IT})
    assert summarize([had]) == Totals(0, 0, 0, 0, 0, 1, None)


def test_summarize_of_nothing() -> None:
    assert summarize([]) == Totals(0, 0, 0, 0, 0, 0, None)


@pytest.mark.parametrize(
    ("fields", "error"),
    [
        ((-1, 0, -1, 0, 0, 0, None), ValueError),
        ((100, 10, 100, 0, 0, 0, None), ValueError),  # total + savings != regular_total
        ((cast(Any, 1.5), 0, 0, 0, 0, 0, None), TypeError),
        ((cast(Any, True), 0, 1, 0, 0, 0, None), TypeError),
        ((0, 0, 0, 0, 0, 0, datetime(2026, 10, 6)), ValueError),  # noqa: DTZ001 - on purpose
    ],
)
def test_totals_hold_only_sane_values(fields: tuple[Any, ...], error: type[Exception]) -> None:
    with pytest.raises(error):
        Totals(*fields)


@pytest.mark.parametrize(
    ("totals", "lines"),
    [
        (
            Totals(14149, 0, 14149, 1, 0, 0, MORNING),
            (
                "About $141",
                "Prices as of 9:14 AM",
                "Before tax, fees and tip",
                "1 item has no price",
            ),
        ),
        (
            Totals(142150, 40, 142190, 0, 0, 0, MORNING),
            (
                "About $1,422",
                "$0.40 off on sale",
                "Prices as of 9:14 AM",
                "Before tax, fees and tip",
            ),
        ),
        (
            Totals(2269, 150, 2419, 0, 0, 0, None),
            ("About $23", "$1.50 off on sale", "Before tax, fees and tip"),
        ),
        (
            Totals(14150, 123456, 137606, 0, 0, 0, None),
            ("About $142", "$1,235 off on sale", "Before tax, fees and tip"),
        ),
        (Totals(40, 0, 40, 0, 0, 0, None), ("Less than $1", "Before tax, fees and tip")),
        (
            Totals(0, 0, 0, 2, 0, 0, None),
            ("About $0", "Before tax, fees and tip", "2 items have no price"),
        ),
    ],
)
def test_headline_lines(totals: Totals, lines: tuple[str, ...]) -> None:
    assert headline_lines(totals, "9:14 AM") == lines


def test_the_headline_leaves_out_the_time_when_it_has_none() -> None:
    assert "Prices as of" not in headline(Totals(100, 0, 100, 0, 0, 0, MORNING), "")
    assert headline(Totals(100, 0, 100, 0, 0, 0, None), "9:14 AM").splitlines()[0] == "About $1"
