"""Builders shared by the domain tests. All data is synthetic."""

from __future__ import annotations

from datetime import UTC, datetime
from fractions import Fraction

from dinnerbell.domain.amounts import AmountOptions
from dinnerbell.domain.models import Amount, AmountKind, Item, Product, SoldBy
from dinnerbell.domain.money import PriceInfo
from dinnerbell.domain.rational import q
from dinnerbell.domain.sizes import PackageSize
from dinnerbell.domain.units import Unit

NOW = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)  # PLAN §8.5: every case uses this instant

# Size strings in the shapes Kroger sends, good and bad (PLAN §8.3), for cases that need many.
SIZE_CORPUS: tuple[str | None, ...] = (
    "16 oz",
    "8 oz bag",
    "2 lb",
    "0.75 lb",
    "3 lb bag",
    "about 1.25 lb",
    "1 lb 8 oz",
    "64 oz",
    "6 ct",
    "18 ct",
    "each",
    "1 ea",
    "1 dozen",
    "4 rolls",
    "1 bunch",
    "1 gal",
    "1/2 gal",
    "64 fl oz",
    "16.9 FL. OZ.",
    "16 fl oz (473 mL)",
    "1 L",
    "500 mL",
    "12 x 12 fl oz",
    "6 ct / 16.9 fl oz",
    "8 x 1.5 oz",
    "2 x 6 ct",
    "per lb",
    "Varies",
    "",
    "3-4 lb",
    "2 cu ft",
    "0 oz",
    "12 oz, 2 ct",
    None,
)


def product(
    size_text: str | None,
    *,
    sold_by: SoldBy = SoldBy.UNIT,
    regular: int | None = 250,
    promo: int | None = None,
    promo_from: datetime | None = None,
    promo_until: datetime | None = None,
    each_estimate: Fraction | None = None,
    priced: bool = True,
    product_id: str = "0000000000001",
) -> Product:
    price = (
        PriceInfo(
            regular=regular,
            promo=promo,
            promo_from=promo_from,
            promo_until=promo_until,
            each_estimate=each_estimate,
            fetched_at=NOW,
        )
        if priced
        else None
    )
    return Product(product_id, size_text, sold_by, price)


def by_weight(
    regular: int | None = 149,
    *,
    promo: int | None = None,
    each_estimate: Fraction | None = None,
    product_id: str = "0000000000001",
) -> Product:
    """A product sold by the pound, like loose onions."""
    return product(
        "per lb",
        sold_by=SoldBy.WEIGHT,
        regular=regular,
        promo=promo,
        each_estimate=each_estimate,
        product_id=product_id,
    )


def item(
    *,
    each_weight: str | None = None,
    size: PackageSize | None = None,
    name: str = "Sample Item",
    item_id: str = "item-1",
) -> Item:
    return Item(item_id, name, size, None if each_weight is None else q(each_weight))


def packages(value: str) -> Amount:
    return Amount(AmountKind.PACKAGES, q(value))


def measure(value: str, unit: Unit) -> Amount:
    return Amount(AmountKind.MEASURE, q(value), unit)


def count(value: str) -> Amount:
    return Amount(AmountKind.COUNT, q(value))


def offered_amounts(options: AmountOptions) -> list[Amount]:
    """Every amount the picker can produce from these options: presets, steps and units."""
    amounts: list[Amount] = []
    for option in options.kinds:
        amounts.extend(option.presets)
        if option.step is not None:
            amounts += [Amount(option.kind, option.step), Amount(option.kind, option.step * 7)]
        for unit in option.units:
            amounts += [
                Amount(option.kind, Fraction(1), unit),
                Amount(option.kind, Fraction(5, 2), unit),
            ]
    return amounts
