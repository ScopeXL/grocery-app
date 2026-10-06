"""models.py: amounts, items, products and the effective size (PLAN §8.2)."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, cast

import pytest

from dinnerbell.domain.models import (
    Amount,
    AmountKind,
    InvalidAmount,
    Item,
    Product,
    SoldBy,
    effective_size,
)
from dinnerbell.domain.sizes import PackageSize, ParseFail, Unparseable, parse_size
from dinnerbell.domain.units import Quantity, Unit
from tests.domain.builders import count, measure, packages, product


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda: packages("0"), "Choose an amount more than zero."),
        (lambda: count("-1"), "Choose an amount more than zero."),
        (lambda: Amount(AmountKind.MEASURE, Fraction(1)), "Choose a unit for this amount"),
        (lambda: measure("1", Unit.EACH), "Choose a unit for this amount"),
        (
            lambda: Amount(AmountKind.PACKAGES, Fraction(1), Unit.OZ),
            "Parts of a package and counts don't take a unit.",
        ),
        (
            lambda: Amount(AmountKind.COUNT, Fraction(3), Unit.EACH),
            "Parts of a package and counts don't take a unit.",
        ),
    ],
)
def test_an_amount_is_always_usable(build: Any, message: str) -> None:
    with pytest.raises(InvalidAmount) as caught:
        build()
    assert caught.value.message.startswith(message)
    assert isinstance(caught.value, ValueError)


def test_amounts_scale_exactly() -> None:
    three_quarters = packages("3/4")
    assert three_quarters.scaled(Fraction(1, 2)) == packages("3/8")
    assert three_quarters.scaled(Fraction(2)).scaled(Fraction(1, 2)) == three_quarters.scaled(
        Fraction(1)
    )
    assert measure("6", Unit.OZ).scaled(Fraction(2)) == measure("12", Unit.OZ)
    with pytest.raises(ValueError):
        three_quarters.scaled(Fraction(0))


def test_an_amount_knows_its_quantity() -> None:
    assert measure("6", Unit.OZ).quantity == Quantity(Fraction(6), Unit.OZ)
    assert count("3").quantity is None
    assert packages("1/2").quantity is None


def test_the_household_size_wins_over_the_product_size() -> None:
    juice = PackageSize(None, Quantity(Fraction(64), Unit.FL_OZ))
    sold_as_ounces = product("64 oz")
    assert effective_size(Item("item-1", "Sample Juice"), sold_as_ounces) == parse_size("64 oz")
    assert effective_size(Item("item-1", "Sample Juice", juice), sold_as_ounces) == juice
    assert effective_size(Item("item-1", "Sample Juice", juice), None) == juice
    assert effective_size(Item("item-1", "Sample Juice"), None) == Unparseable("", ParseFail.EMPTY)


def test_an_item_holds_a_real_each_weight_and_size() -> None:
    assert Item("item-1", "Sample Onion", each_weight=Fraction(1, 2)).each_weight == Fraction(1, 2)
    with pytest.raises(ValueError, match="more than zero"):
        Item("item-1", "Sample Onion", each_weight=Fraction(0))
    with pytest.raises(TypeError):
        Item("item-1", "Sample Onion", size_override=cast(Any, parse_size("Varies")))


def test_sold_by_reads_kroger_casing() -> None:
    assert SoldBy(cast(Any, "WEIGHT")) is SoldBy.WEIGHT
    assert SoldBy(cast(Any, "Unit")) is SoldBy.UNIT
    assert Product("0000000000001", "16 oz", cast(Any, "WEIGHT")).sold_by is SoldBy.WEIGHT
    with pytest.raises(ValueError):
        SoldBy(cast(Any, "BUNCH"))
