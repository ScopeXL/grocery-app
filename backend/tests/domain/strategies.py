"""Hypothesis strategies for the domain (PLAN §8.6). Everything here is synthetic.

Items come from a pool of 5 ids, so that plans built from them (M2) are forced to merge lines.
Quantities are fractions with denominators up to 64; prices are 1 to 5000 cents.
"""

from __future__ import annotations

from datetime import timedelta
from fractions import Fraction

from hypothesis import strategies as st

from dinnerbell.domain.models import Amount, AmountKind, Item, Product, SoldBy
from dinnerbell.domain.money import PriceInfo
from dinnerbell.domain.sizes import Container, PackageSize, format_size
from dinnerbell.domain.units import Dimension, Quantity, Unit
from tests.domain.builders import NOW, SIZE_CORPUS

ITEM_IDS = tuple(f"item-{n}" for n in range(1, 6))
PRODUCT_IDS = tuple(f"00000000000{n:02d}" for n in range(1, 6))
MEASURE_UNITS = tuple(unit for unit in Unit if unit.dimension is not Dimension.COUNT)


def positive_fractions(max_value: int = 500) -> st.SearchStrategy[Fraction]:
    return st.fractions(
        min_value=Fraction(1, 64), max_value=Fraction(max_value), max_denominator=64
    )


def cents() -> st.SearchStrategy[int]:
    return st.integers(min_value=1, max_value=5000)


def quantities(units: tuple[Unit, ...] = tuple(Unit)) -> st.SearchStrategy[Quantity]:
    return st.builds(Quantity, positive_fractions(), st.sampled_from(units))


@st.composite
def package_sizes(draw: st.DrawFn) -> PackageSize:
    shape = draw(st.sampled_from(("count", "measure", "multipack")))
    count = None if shape == "measure" else draw(positive_fractions())
    measure = None if shape == "count" else draw(quantities(MEASURE_UNITS))
    container = draw(st.none() | st.sampled_from(tuple(Container)))
    return PackageSize(count, measure, draw(st.booleans()), container)


def size_texts() -> st.SearchStrategy[str | None]:
    """Realistic sizes, sizes written by format_size, and arbitrary text."""
    return st.one_of(
        st.sampled_from(SIZE_CORPUS),
        package_sizes().map(format_size),
        st.text(max_size=24),
    )


@st.composite
def prices(draw: st.DrawFn) -> PriceInfo:
    around_now = st.none() | st.sampled_from(
        (NOW - timedelta(days=1), NOW, NOW + timedelta(days=1))
    )
    return PriceInfo(
        regular=draw(st.none() | st.just(0) | cents()),
        promo=draw(st.none() | st.just(0) | cents()),
        promo_from=draw(around_now),
        promo_until=draw(around_now),
        each_estimate=draw(st.none() | positive_fractions(5000)),
        fetched_at=NOW,
    )


def products() -> st.SearchStrategy[Product]:
    return st.builds(
        Product,
        product_id=st.sampled_from(PRODUCT_IDS),
        size_text=size_texts(),
        sold_by=st.sampled_from(tuple(SoldBy)),
        price=st.none() | prices(),
    )


def items() -> st.SearchStrategy[Item]:
    return st.builds(
        Item,
        id=st.sampled_from(ITEM_IDS),
        name=st.just("Sample Item"),
        size_override=st.none() | package_sizes(),
        each_weight=st.none() | positive_fractions(5),
    )


@st.composite
def amounts(draw: st.DrawFn) -> Amount:
    kind = draw(st.sampled_from(tuple(AmountKind)))
    unit = draw(st.sampled_from(MEASURE_UNITS)) if kind is AmountKind.MEASURE else None
    return Amount(kind, draw(positive_fractions()), unit)
