"""The list's totals (PLAN §8.4): what it costs, what sales save, and what couldn't be priced."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

from .models import Flag
from .money import require_aware


class PricedLine(Protocol):
    """What ``summarize`` reads from a list line (``listbuild.Line`` has all of it)."""

    @property
    def cost_cents(self) -> int | None: ...
    @property
    def regular_cents(self) -> int | None: ...
    @property
    def savings_cents(self) -> int: ...
    @property
    def at_least(self) -> bool: ...
    @property
    def price_fetched_at(self) -> datetime | None: ...
    @property
    def flags(self) -> frozenset[Flag]: ...


@dataclass(frozen=True, slots=True)
class Totals:
    """Cents are ints >= 0, and ``total + savings == regular_total``."""

    total: int  # what the priced lines cost, sales included ("About $142")
    savings: int  # what sales take off ("$11 off on sale")
    regular_total: int  # the same lines at regular prices
    not_priced: int  # lines (not have-it) with no price, or only a lower bound ("at least")
    needs_check: int  # lines (not have-it) whose swap couldn't be compared ("check amount")
    have_it: int  # lines the household already has
    prices_as_of: datetime | None  # the OLDEST price among priced lines

    def __post_init__(self) -> None:
        for name in ("total", "savings", "regular_total", "not_priced", "needs_check", "have_it"):
            value = cast(object, getattr(self, name))
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
            if value < 0:
                raise ValueError(f"{name} can't be negative")
        if self.total + self.savings != self.regular_total:
            raise ValueError("total + savings must equal regular_total")
        if self.prices_as_of is not None:
            require_aware(self.prices_as_of, "prices_as_of")


def summarize(lines: Iterable[PricedLine]) -> Totals:
    """Add up the lines that have a cost and aren't have-it, and count the rest (PLAN §8.4)."""
    total = savings = regular = not_priced = needs_check = have_it = 0
    oldest: datetime | None = None
    for line in lines:
        if Flag.HAVE_IT in line.flags:
            have_it += 1
            continue
        if Flag.APPROX_SWAP in line.flags:
            needs_check += 1
        cost = line.cost_cents
        if cost is None or line.at_least:
            not_priced += 1  # an "at least" line still adds its lower bound below
        if cost is None:
            continue
        total += cost
        savings += line.savings_cents
        regular += cost if line.regular_cents is None else line.regular_cents
        fetched = line.price_fetched_at
        if fetched is not None and (oldest is None or fetched < oldest):
            oldest = fetched
    return Totals(total, savings, regular, not_priced, needs_check, have_it, oldest)
