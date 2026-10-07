"""Hypothesis strategies for the domain (PLAN §8.6). Everything here is synthetic.

Items come from a pool of 5 ids, so that plans built from them (M2) are forced to merge lines.
Quantities are fractions with denominators up to 64; prices are 1 to 5000 cents.
"""

from __future__ import annotations

from datetime import timedelta
from fractions import Fraction

from hypothesis import strategies as st

from dinnerbell.domain.amounts import amount_options
from dinnerbell.domain.models import (
    Amount,
    AmountKind,
    Dish,
    DishLine,
    Extra,
    Item,
    Meal,
    PlanInput,
    Product,
    PurchaseUnit,
    QuantityOverride,
    SoldBy,
)
from dinnerbell.domain.money import PriceInfo
from dinnerbell.domain.sizes import Container, PackageSize, format_size
from dinnerbell.domain.units import Dimension, Quantity, Unit
from tests.domain.builders import NOW, SIZE_CORPUS, offered_amounts

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


# ---- plans (M2) ----------------------------------------------------------------------------------

SCALES = (Fraction(1, 2), Fraction(1), Fraction(2))
DISH_NAMES = ("Tacos", "Chili", "Rice", "Salad", "Soup")
LIST_SIZES = (  # sizes shopping lists meet, readable or not
    "16 oz",
    "8 oz bag",
    "1 lb",
    "3 lb bag",
    "about 1.25 lb",
    "64 fl oz",
    "1 gal",
    "6 ct",
    "each",
    "12 ct box",
    "12 x 12 fl oz",
    "8 x 1.5 oz",
    "per lb",
    "Varies",
)
SIMPLE_SIZES = ("16 oz", "1 lb", "3.3 oz", "64 fl oz", "1 gal", "6 ct", "each", "12 x 12 fl oz")
SWAP_IDS = tuple(f"00000000000{n:02d}" for n in range(91, 94))
DELTAS = tuple(Fraction(n, 4) for n in (-8, -4, -1, 0, 1, 4, 8))


def overrides() -> st.SearchStrategy[QuantityOverride]:
    return st.builds(
        QuantityOverride, st.sampled_from(DELTAS), st.sampled_from(tuple(PurchaseUnit))
    )


def list_products(product_ids: tuple[str, ...]) -> st.SearchStrategy[Product]:
    return st.builds(
        Product,
        product_id=st.sampled_from(product_ids),
        size_text=st.sampled_from(LIST_SIZES) | size_texts(),
        sold_by=st.sampled_from(tuple(SoldBy)),
        price=st.none() | prices(),
    )


@st.composite
def plans(
    draw: st.DrawFn,
    *,
    unit_sold_only: bool = False,
    extras: bool = True,
    have_it: bool = True,
    adjust: bool = True,
    swaps: bool = True,
) -> PlanInput:
    """A plan over the pool of 5 items. ``unit_sold_only`` gives readable unit-sold sizes and
    amounts the picker offers (for the naive cross-check); ``adjust`` adds overrides."""
    stock: dict[str, tuple[Item, Product | None]] = {}
    for n, item_id in enumerate(ITEM_IDS):
        name = f"Sample item {n + 1}"
        if unit_sold_only:
            price = PriceInfo(
                regular=draw(cents()), promo=draw(st.none() | cents()), fetched_at=NOW
            )
            size = draw(st.sampled_from(SIMPLE_SIZES))
            stock[item_id] = (
                Item(item_id, name),
                Product(PRODUCT_IDS[n], size, SoldBy.UNIT, price),
            )
        else:
            item = Item(
                item_id,
                name,
                size_override=draw(st.one_of(st.none(), st.none(), package_sizes())),
                each_weight=draw(st.none() | positive_fractions(5)),
            )
            stock[item_id] = (item, draw(st.none() | list_products((PRODUCT_IDS[n],))))

    def amount_for(item_id: str) -> Amount:
        if not unit_sold_only:
            return draw(amounts())
        item, product = stock[item_id]
        return draw(st.sampled_from(offered_amounts(amount_options(item, product))))

    meals: list[Meal] = []
    for m in range(draw(st.integers(0, 4))):
        dishes: list[Dish] = []
        for d in range(draw(st.integers(1, 3))):
            used = draw(st.lists(st.sampled_from(ITEM_IDS), max_size=4))
            lines = tuple(DishLine(item_id, amount_for(item_id)) for item_id in used)
            dishes.append(Dish(f"dish-{m}-{d}", draw(st.sampled_from(DISH_NAMES)), lines))
        meals.append(Meal(f"meal-{m}", dishes[0], tuple(dishes[1:]), draw(st.sampled_from(SCALES))))

    added: list[Extra] = []
    if extras:
        for k in range(draw(st.integers(0, 3))):
            item_id = draw(st.none() | st.sampled_from(ITEM_IDS))
            text = "birthday candles" if item_id is None else None
            added.append(Extra(f"extra-{k}", item_id, text, Fraction(draw(st.integers(1, 3)))))
    return PlanInput(
        meals=tuple(meals),
        items={item_id: item for item_id, (item, _) in stock.items()},
        products={item_id: product for item_id, (_, product) in stock.items()},
        have_it=draw(st.frozensets(st.sampled_from(ITEM_IDS), max_size=2))
        if have_it
        else frozenset(),
        overrides=(
            draw(st.dictionaries(st.sampled_from(ITEM_IDS), overrides(), max_size=2))
            if adjust
            else {}
        ),
        swaps=(
            draw(st.dictionaries(st.sampled_from(ITEM_IDS), list_products(SWAP_IDS), max_size=2))
            if swaps and not unit_sold_only
            else {}
        ),
        extras=tuple(added),
    )


@st.composite
def new_meals(draw: st.DrawFn) -> Meal:
    """One more meal for a plan from ``plans()``, over the same 5 items."""
    used = draw(st.lists(st.sampled_from(ITEM_IDS), min_size=1, max_size=4))
    lines = tuple(DishLine(item_id, draw(amounts())) for item_id in used)
    return Meal(
        "meal-new", Dish("dish-new", "Sample new dish", lines), (), draw(st.sampled_from(SCALES))
    )
