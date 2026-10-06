"""Items, the store products they link to, and amounts (PLAN §8.2).

An ``Item`` is the household's own record. A ``Product`` is Kroger's data for it, which is only an
expiring cache (ADR 0016), so the two are separate and are passed in side by side.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import cast

from .money import PriceInfo
from .rational import q
from .sizes import PackageSize, Unparseable, parse_size
from .units import Dimension, Quantity, Unit


class SoldBy(StrEnum):
    UNIT = "unit"  # priced per package
    WEIGHT = "weight"  # priced per pound

    @classmethod
    def _missing_(cls, value: object) -> SoldBy | None:
        # Kroger's casing varies ("UNIT", "Weight"), so look values up case-insensitively.
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None


class AmountKind(StrEnum):
    PACKAGES = "packages"  # part of a package: 1/2 bag
    MEASURE = "measure"  # a weight or volume: 6 oz, 2 cups
    COUNT = "count"  # pieces: 3 onions


class Flag(StrEnum):
    """Why a list line needs a second look.

    ``contribution`` sets SIZE_UNKNOWN, NEEDS_EACH_WEIGHT, NOT_CONVERTIBLE and APPROX_SWAP; the
    list builder (M2) sets the rest. They live here so both can use them.
    """

    NO_PRODUCT = "no_product"
    NO_PRICE = "no_price"
    SIZE_UNKNOWN = "size_unknown"
    NEEDS_EACH_WEIGHT = "needs_each_weight"
    NOT_CONVERTIBLE = "not_convertible"
    EST_EACH_WEIGHT = "est_each_weight"
    SWAPPED = "swapped"
    APPROX_SWAP = "approx_swap"
    OVERRIDDEN = "overridden"
    OVERRIDE_STALE = "override_stale"
    SHORT = "short"
    HAVE_IT = "have_it"
    ON_SALE = "on_sale"


class InvalidAmount(ValueError):  # noqa: N818 - the name PLAN §8.2 uses
    """An amount that can't be used for this item. ``message`` is plain English for the person."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class Product:
    """Only what the math needs from Kroger's product data."""

    product_id: str
    size_text: str | None  # Kroger's size string, exactly as returned
    sold_by: SoldBy
    price: PriceInfo | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sold_by", SoldBy(self.sold_by))


@dataclass(frozen=True, slots=True)
class Item:
    """Something the household buys. Its own size and each-weight win over Kroger's data."""

    id: str
    name: str
    size_override: PackageSize | None = None  # the household's corrected or confirmed size
    each_weight: Fraction | None = None  # pounds per piece, set by the household

    def __post_init__(self) -> None:
        size = cast(object, self.size_override)
        if size is not None and not isinstance(size, PackageSize):
            raise TypeError("size_override must be a PackageSize")
        if self.each_weight is not None:
            weight = q(self.each_weight)
            if weight <= 0:
                raise ValueError("One piece must weigh more than zero.")
            object.__setattr__(self, "each_weight", weight)


@dataclass(frozen=True, slots=True)
class Amount:
    """How much of an item a dish line needs: 1/2 (packages), 6 oz (measure) or 3 (count)."""

    kind: AmountKind
    value: Fraction  # always more than zero
    unit: Unit | None = None  # a weight or volume unit for MEASURE; None otherwise

    def __post_init__(self) -> None:
        value = q(self.value)
        kind = AmountKind(self.kind)
        unit = None if self.unit is None else Unit(self.unit)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "unit", unit)
        if value <= 0:
            raise InvalidAmount("Choose an amount more than zero.")
        if kind is AmountKind.MEASURE:
            if unit is None or unit.dimension is Dimension.COUNT:
                raise InvalidAmount("Choose a unit for this amount, like ounces or cups.")
        elif unit is not None:
            raise InvalidAmount("Parts of a package and counts don't take a unit.")

    @property
    def quantity(self) -> Quantity | None:
        """The amount as a weight or volume (MEASURE only)."""
        return None if self.unit is None else Quantity(self.value, self.unit)

    def scaled(self, k: Fraction) -> Amount:
        """The amount for a meal planned at k times its size (k = 1/2, 1 or 2)."""
        factor = q(k)
        if factor <= 0:
            raise ValueError("a scale must be more than zero")
        return Amount(self.kind, self.value * factor, self.unit)


def effective_size(item: Item, product: Product | None) -> PackageSize | Unparseable:
    """The household's size if it set one, else the product's size text, parsed."""
    if item.size_override is not None:
        return item.size_override
    return parse_size(None if product is None else product.size_text)
