"""Prices in integer cents (PLAN §8.1, §8.4).

Kroger's JSON is parsed with ``parse_float=Decimal`` and becomes cents at the boundary. Rounding is
half-up, and happens only where the plan says: each weight-priced line, and the "about $N" shown.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from typing import cast

from .rational import q, round_half_up


@dataclass(frozen=True, slots=True, kw_only=True)
class PriceInfo:
    """One product's price at one store. Cents are ints >= 0; times are timezone-aware."""

    regular: int | None  # missing or 0 means "no price"
    promo: int | None = None  # a sale price, not a discount; trusted only when promo_valid()
    promo_from: datetime | None = None  # the promo runs over [promo_from, promo_until)
    promo_until: datetime | None = None
    each_estimate: Fraction | None = None  # Kroger's regularPerUnitEstimate, in (exact) cents
    fetched_at: datetime

    def __post_init__(self) -> None:
        _check_cents(self.regular, "regular")
        _check_cents(self.promo, "promo")
        for name, when in (("promo_from", self.promo_from), ("promo_until", self.promo_until)):
            if when is not None:
                require_aware(when, name)
        require_aware(self.fetched_at, "fetched_at")
        if self.each_estimate is not None:
            estimate = q(self.each_estimate)
            if estimate < 0:
                raise ValueError("each_estimate can't be negative")
            object.__setattr__(self, "each_estimate", estimate)


def dollars_to_cents(d: Decimal | int | str | None) -> int | None:
    """Kroger dollars to whole cents: ``Decimal("1.15")`` -> 115. None, zero or less -> None.

    Exact (``int(1.15 * 100)`` would give 114). A sub-cent price rounds half-up.
    """
    if d is None:
        return None
    dollars = q(d)
    if dollars <= 0:
        return None
    return round_half_up(dollars * 100)


def dollars_to_exact_cents(d: Decimal | int | str | None) -> Fraction | None:
    """Kroger dollars to exact cents, for the per-each estimate: ``"0.0995"`` -> 199/20."""
    if d is None:
        return None
    dollars = q(d)
    return dollars * 100 if dollars > 0 else None


def promo_valid(p: PriceInfo, now: datetime) -> bool:
    """A promo counts only when it is above 0, below the regular price, and within its dates."""
    require_aware(now)
    regular, promo = p.regular, p.promo
    if regular is None or promo is None or not 0 < promo < regular:
        return False
    if p.promo_from is not None and now < p.promo_from:
        return False
    return p.promo_until is None or now < p.promo_until


def effective_cents(p: PriceInfo, now: datetime) -> int:
    """The price to charge now: the promo when it is valid, else the regular price."""
    if p.regular is None:
        raise ValueError("there is no regular price; check for one first")
    promo = p.promo
    if promo is not None and promo_valid(p, now):
        return promo
    return p.regular


def about_dollars(cents: int) -> int:
    """Whole dollars for "about $N", rounded half-up: 14150 -> 142, 14149 -> 141."""
    value = cast(object, cents)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("cents must be an int")
    return round_half_up(Fraction(value, 100))


def require_aware(when: datetime, name: str = "now") -> datetime:
    """Return ``when``, or raise ValueError if it isn't a timezone-aware datetime."""
    value = cast(object, when)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value


def _check_cents(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be whole cents (an int)")
    if value < 0:
        raise ValueError(f"{name} can't be negative")
