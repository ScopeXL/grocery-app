"""Property tests (PLAN §8.6): 1 and 2 for M1, 14 for every constructor, and the picker promise."""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dinnerbell.domain.amounts import (
    Contribution,
    EachWeightQuestion,
    KindOption,
    amount_options,
    contribution,
    share_cost,
    share_text,
    validate_amount,
)
from dinnerbell.domain.models import Amount, AmountKind, InvalidAmount, Item, Product
from dinnerbell.domain.money import (
    PriceInfo,
    about_dollars,
    dollars_to_cents,
    dollars_to_exact_cents,
)
from dinnerbell.domain.rational import ceil_to, q, round_half_up, to_text
from dinnerbell.domain.sizes import PackageSize, Unparseable, format_size, parse_size
from dinnerbell.domain.units import DimensionMismatch, Quantity, Unit, convert
from tests.domain.builders import NOW, offered_amounts
from tests.domain.strategies import (
    amounts,
    items,
    package_sizes,
    positive_fractions,
    products,
    quantities,
    size_texts,
)

# ---- 1: parse_size never raises, and parse(format(s)) == s --------------------------------------


@settings(max_examples=500)
@given(st.text())
def test_1_parse_size_never_raises(text: str) -> None:
    result = parse_size(text)
    if isinstance(result, Unparseable):
        assert result.text == text  # kept as given, for "Fix size"


@settings(max_examples=300)
@given(size_texts())
def test_1_a_parsed_size_survives_format_and_parse(text: str | None) -> None:
    size = parse_size(text)
    if isinstance(size, PackageSize):
        assert parse_size(format_size(size)) == size


@settings(max_examples=500)
@given(package_sizes())
def test_1_format_then_parse_gives_back_the_same_size(size: PackageSize) -> None:
    assert parse_size(format_size(size)) == size


# ---- 2: unit conversion is exact and never crosses dimensions -----------------------------------


@given(quantities(), st.sampled_from(tuple(Unit)))
def test_2_converting_there_and_back_is_identical(x: Quantity, unit: Unit) -> None:
    if unit.dimension is x.dimension:
        assert convert(convert(x, unit), x.unit) == x
    else:
        with pytest.raises(DimensionMismatch):
            convert(x, unit)


# ---- 14: every public constructor rejects floats ------------------------------------------------

FLOAT_TAKERS: dict[str, Callable[[Any], object]] = {
    "q": q,
    "ceil_to": lambda f: ceil_to(f, Fraction(1, 4)),
    "round_half_up": round_half_up,
    "to_text": to_text,
    "Quantity": lambda f: Quantity(f, Unit.OZ),
    "PackageSize.count": lambda f: PackageSize(f, None),
    "PackageSize.measure": lambda f: PackageSize(None, Quantity(f, Unit.OZ)),
    "Item.each_weight": lambda f: Item("item-1", "Sample Item", each_weight=f),
    "Amount": lambda f: Amount(AmountKind.PACKAGES, f),
    "Amount.scaled": lambda f: Amount(AmountKind.PACKAGES, Fraction(1)).scaled(f),
    "PriceInfo.regular": lambda f: PriceInfo(regular=f, fetched_at=NOW),
    "PriceInfo.promo": lambda f: PriceInfo(regular=100, promo=f, fetched_at=NOW),
    "PriceInfo.each_estimate": lambda f: PriceInfo(regular=100, each_estimate=f, fetched_at=NOW),
    "dollars_to_cents": dollars_to_cents,
    "dollars_to_exact_cents": dollars_to_exact_cents,
    "about_dollars": about_dollars,
    "Contribution": lambda f: Contribution(packages=f),
    "KindOption.step": lambda f: KindOption(AmountKind.COUNT, step=f),
    "EachWeightQuestion.presets": lambda f: EachWeightQuestion(presets=(f,), prefill=None),
    "EachWeightQuestion.prefill": lambda f: EachWeightQuestion(presets=(), prefill=f),
}


@given(st.floats())
def test_14_public_constructors_reject_floats(value: float) -> None:
    for name, take in FLOAT_TAKERS.items():
        with pytest.raises(TypeError):
            take(value)
            pytest.fail(f"{name} accepted the float {value!r}")


# ---- the picker never offers what contribution can't convert (PLAN §8.7) -------------------------


@settings(max_examples=400)
@given(items(), st.none() | products())
def test_every_offered_amount_converts(item: Item, product: Product | None) -> None:
    options = amount_options(item, product)
    assert options.kinds
    assert len({option.kind for option in options.kinds}) == len(options.kinds)
    for a in offered_amounts(options):
        assert contribution(a, item, product, product).converted, a
        validate_amount(a, item, product)
        assert share_text(a, item, product) is not None, a
        cost = share_cost(a, item, product, NOW)
        assert cost is None or cost >= 0


@settings(max_examples=300)
@given(amounts(), items(), st.none() | products())
def test_validation_and_conversion_agree(a: Amount, item: Item, product: Product | None) -> None:
    converted = contribution(a, item, product, product)
    try:
        validate_amount(a, item, product)
    except InvalidAmount as rejected:
        assert not converted.converted
        assert share_text(a, item, product) is None
        assert rejected.message.endswith(".")
    else:
        assert converted.converted
        assert share_text(a, item, product) is not None


@given(amounts(), items(), products(), products())
def test_a_swap_always_gives_a_line(
    a: Amount, item: Item, product: Product, original: Product
) -> None:
    swapped = contribution(a, item, product, original, swapped=True)
    filled = [v for v in (swapped.packages, swapped.lb, swapped.each) if v]
    assert len(filled) <= 1
    assert swapped.converted == bool(filled)


@given(amounts(), positive_fractions(4))
def test_scaling_by_k_then_back_is_exact(a: Amount, k: Fraction) -> None:
    assert a.scaled(k).scaled(1 / k) == a
