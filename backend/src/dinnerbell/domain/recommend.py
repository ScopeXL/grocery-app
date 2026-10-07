"""Recommendations: mains that use up what this week's list leaves over (PLAN §8.4).

Each candidate is priced by rebuilding the whole list with it added, so merging, rounding and
pricing follow the list's own rules exactly. Its value is the part of the leftovers it would use:
packages (or pounds, or pieces) the plan buys anyway and wouldn't otherwise finish.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from fractions import Fraction
from typing import cast

from .listbuild import Line, ShoppingList, build_list
from .models import Dish, Meal, PlanInput, PurchaseUnit
from .money import about_dollars, require_aware
from .rational import round_half_up

ROLES = ("main", "side")
_ZERO = Fraction(0)
_NAMED_AT_MOST = 3


@dataclass(frozen=True, slots=True)
class Candidate:
    """A dish that might be recommended, with what ranking needs to know about it."""

    dish: Dish
    role: str  # "main" or "side"; only mains are recommended
    archived: bool = False
    favorite: bool = False
    last_made: date | None = None  # the last day it was planned; None if never

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"role must be 'main' or 'side', not {self.role!r}")
        for name in ("archived", "favorite"):
            if not isinstance(cast(object, getattr(self, name)), bool):
                raise TypeError(f"{name} must be True or False")
        made = cast(object, self.last_made)
        if made is not None and (not isinstance(made, date) or isinstance(made, datetime)):
            raise TypeError("last_made must be a date")


@dataclass(frozen=True, slots=True)
class Recommendation:
    dish_id: str
    name: str
    added_cents: int  # what adding it adds to the total (never below 0)
    unpriced: int  # lines it adds or grows that have no full price (have-it lines aside)
    value_cents: int  # the leftovers it uses, rounded to whole cents
    named: tuple[str, ...]  # item labels named in the sentence, in the dish's line order
    more: int  # nameable items left unnamed ("and 2 more")
    text: str  # "Taco salad uses your leftover lettuce, cheese and ground beef. Adds about $4."

    def __post_init__(self) -> None:
        for name in ("added_cents", "unpriced", "value_cents", "more"):
            value = cast(object, getattr(self, name))
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
            if value < 0:
                raise ValueError(f"{name} can't be negative")
        object.__setattr__(self, "named", tuple(self.named))


def marginal_cost(plan: PlanInput, dish: Dish, now: datetime) -> tuple[int, int]:
    """What planning ``dish`` once more would add: (cents added to the total, never below 0;
    lines it adds or grows that have no full price)."""
    require_aware(now)
    base = build_list(plan, now)
    return _marginal(base, _by_key(base), build_list(plan.with_meal(meal_for(dish)), now))


def recommend(
    plan: PlanInput,
    candidates: Sequence[Candidate],
    now: datetime,
    *,
    limit: int = 3,
    min_value_cents: int = 100,
    name_min_cents: int = 25,
) -> tuple[Recommendation, ...]:
    """Mains that use the list's leftovers, best first, at most ``limit`` (PLAN §8.4, §8.8).

    A main qualifies when it isn't archived or planned already as a main, and uses at least
    ``min_value_cents`` of leftovers (have-it items never count). Meals with unpriced items come
    last; then the displayed "about $N" ranks, so favorites, then meals not made lately, win
    ties. Every candidate's items must be in ``plan.items``.
    """
    require_aware(now)
    for name, value in (
        ("limit", limit),
        ("min_value_cents", min_value_cents),
        ("name_min_cents", name_min_cents),
    ):
        if isinstance(cast(object, value), bool) or not isinstance(cast(object, value), int):
            raise TypeError(f"{name} must be an int")
        if value < 0:
            raise ValueError(f"{name} can't be negative")
    if len({c.dish.id for c in candidates}) != len(candidates):
        raise ValueError("two candidates share a dish id")

    base = build_list(plan, now)
    base_lines = _by_key(base)
    planned = {meal.main.id for meal in plan.meals}
    ranked: list[tuple[tuple[bool, int, bool, date, int, str, str], Recommendation]] = []
    for candidate in candidates:
        dish = candidate.dish
        if candidate.role != "main" or candidate.archived or dish.id in planned:
            continue
        with_dish = build_list(plan.with_meal(meal_for(dish)), now)
        shared = _shared(dish, base_lines, _by_key(with_dish))
        value = sum((cents for _, cents in shared), _ZERO)
        if not shared or value < min_value_cents:
            continue  # nothing shared, or too little ("only the olive oil")
        added, unpriced = _marginal(base, base_lines, with_dish)
        named, more = _named(shared, name_min_cents)
        key = (
            unpriced > 0,
            about_dollars(added),
            not candidate.favorite,
            candidate.last_made or date.min,
            added,
            dish.name.casefold(),
            dish.id,
        )
        text = _sentence(dish.name, named, more, added, unpriced)
        recommendation = Recommendation(
            dish.id, dish.name, added, unpriced, round_half_up(value), named, more, text
        )
        ranked.append((key, recommendation))
    ranked.sort(key=lambda pair: pair[0])
    return tuple(recommendation for _, recommendation in ranked[:limit])


def meal_for(dish: Dish) -> Meal:
    """The meal a recommendation is priced with: the dish alone, at its usual size."""
    return Meal(f"recommend:{dish.id}", dish, (), Fraction(1))


# ---- pricing and leftovers -----------------------------------------------------------------------


def _by_key(shopping: ShoppingList) -> dict[str, Line]:
    return {line.key: line for line in shopping.lines}


def _marginal(
    base: ShoppingList, base_lines: Mapping[str, Line], with_dish: ShoppingList
) -> tuple[int, int]:
    added = max(0, with_dish.totals.total - base.totals.total)
    unpriced = sum(
        1
        for line in with_dish.lines
        if not line.have_it
        and (line.cost_cents is None or line.at_least)
        and _grew(base_lines.get(line.key), line)
    )
    return added, unpriced


def _grew(before: Line | None, after: Line) -> bool:
    """The dish adds this line, or makes it buy more (or more of what can't be priced)."""
    if before is None:
        return True
    return (
        after.unit is not before.unit
        or after.quantity > before.quantity
        or after.unconverted != before.unconverted
    )


def _shared(
    dish: Dish, base_lines: Mapping[str, Line], with_lines: Mapping[str, Line]
) -> list[tuple[str, Fraction]]:
    """(label, cents of leftovers used) for each item the dish shares, in its line order."""
    shared: list[tuple[str, Fraction]] = []
    for item_id in dict.fromkeys(dish_line.item_id for dish_line in dish.lines):
        before, after = base_lines.get(item_id), with_lines.get(item_id)
        if before is None or after is None or before.have_it:
            continue
        cents = _leftover_used(before, after)
        if cents > 0:
            shared.append((before.label, cents))
    return shared


def _leftover_used(before: Line, after: Line) -> Fraction:
    """What the dish uses of ``before``'s leftover, in cents at today's price (0 if unpriced)."""
    left, cents = before.leftover, before.unit_cents
    if left is None or left <= 0 or cents is None:
        return _ZERO
    weight = before.each_weight
    if after.unit is before.unit:
        used = min(after.need - before.need, left)
        if before.unit is PurchaseUnit.EACH:  # pieces, priced per pound
            if weight is None:
                return _ZERO
            used *= weight
    elif before.unit is PurchaseUnit.EACH and after.unit is PurchaseUnit.POUND and weight:
        used = min(after.need - before.need * weight, left * weight)  # pieces became pounds
    else:
        return _ZERO
    return max(_ZERO, used * cents)


def _named(shared: list[tuple[str, Fraction]], name_min_cents: int) -> tuple[tuple[str, ...], int]:
    """The top 3 items worth naming (or the single best), in line order, and how many more."""
    order = range(len(shared))
    nameable = [n for n in order if shared[n][1] >= name_min_cents]
    if nameable:
        top = sorted(nameable, key=lambda n: (-shared[n][1], n))[:_NAMED_AT_MOST]
        more = len(nameable) - len(top)
    else:
        top = [max(order, key=lambda n: (shared[n][1], -n))]
        more = 0
    return tuple(shared[n][0] for n in sorted(top)), more


# ---- words ---------------------------------------------------------------------------------------


def _sentence(name: str, named: tuple[str, ...], more: int, added: int, unpriced: int) -> str:
    """The sentence, e.g. "Taco salad uses your leftover lettuce, cheese and ground beef.
    Adds about $4." """
    things = [_in_a_sentence(label) for label in named]
    if more:
        things.append(f"{more} more")
    return f"{name} uses your leftover {_and_list(things)}. {_cost_words(added, unpriced)}"


def _cost_words(added: int, unpriced: int) -> str:
    without = f"{unpriced} item{'' if unpriced == 1 else 's'} without a price"
    if not added:
        return f"Adds {without}." if unpriced else "Nothing extra to buy."
    dollars = about_dollars(added)
    cost = f"about ${dollars:,}" if dollars else "less than $1"
    return f"Adds {cost}, plus {without}." if unpriced else f"Adds {cost}."


def _in_a_sentence(label: str) -> str:
    """Lower-case the first letter, unless the label starts with initials ("BBQ sauce")."""
    if len(label) > 1 and label[1].isupper():
        return label
    return label[:1].lower() + label[1:]


def _and_list(words: list[str]) -> str:
    """Joined with "and" and no serial comma: "a", "a and b", "a, b and c"."""
    if len(words) < 2:
        return "".join(words)
    return f"{', '.join(words[:-1])} and {words[-1]}"
