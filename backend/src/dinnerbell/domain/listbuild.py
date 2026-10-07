"""The shopping list: merge every meal's amounts per item, then round up once (PLAN §8.4).

One line per item. Packages, pieces and pounds are summed exactly across meals, dishes and lines,
then rounded up a single time: whole packages for things sold by the package, whole pieces plus
1/4 lb steps for things sold by the pound. Amounts that can't be converted keep the line on the
list as "at least N". Money is integer cents; a weight-priced line rounds half-up once.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import cast

from .amounts import contribution, resolve_each_weight
from .models import (
    Amount,
    AmountKind,
    Extra,
    Flag,
    Item,
    PlanInput,
    Product,
    PurchaseUnit,
    SoldBy,
    effective_size,
)
from .money import effective_cents, promo_valid, require_aware
from .rational import ceil_to, q, round_half_up, to_mixed
from .sizes import Container, PackageSize, Unparseable, parse_size
from .totals import Totals, summarize
from .units import Dimension, Quantity, Unit, convert

_ZERO = Fraction(0)
_QUARTER_POUND = Fraction(1, 4)
_STEP = {  # the smallest amount a line can buy
    PurchaseUnit.PACKAGE: Fraction(1),
    PurchaseUnit.EACH: Fraction(1),
    PurchaseUnit.POUND: _QUARTER_POUND,
}
_KIND_ORDER = {kind: n for n, kind in enumerate(AmountKind)}
_UNIT_ORDER = {unit: n for n, unit in enumerate(Unit)}


@dataclass(frozen=True, slots=True)
class MealUse:
    """A meal that uses the item, and its dishes that do, in line order ("for Tacos")."""

    meal_id: str
    dish_names: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "dish_names", tuple(self.dish_names))


@dataclass(frozen=True, slots=True, kw_only=True)
class Line:
    """One line of the shopping list: one item, or one plain-text extra.

    Quantities are in ``unit``. ``computed`` is what the plan and extras call for; ``quantity``
    adds the household's override. A have-it line keeps its quantity but costs nothing.
    """

    key: str  # the item id, or "extra:<id>" for a plain-text extra
    item_id: str | None
    label: str  # the item's name, or the extra's text
    unit: PurchaseUnit
    need: Fraction  # what the meals use (only the converted part when ``at_least``)
    computed: Fraction  # what to buy for the meals plus extras, before any override
    quantity: Fraction  # what to buy
    extra: Fraction  # added outside meals; never counted as leftover
    at_least: bool  # some amounts couldn't be converted, so ``quantity`` is a lower bound
    leftover: Fraction | None  # bought for meals minus need; None for have-it or "at least"
    leftover_count: Fraction | None  # a positive leftover in pieces, when that's known
    leftover_measure: Quantity | None  # a positive leftover as a weight or volume ("14 oz")
    each_weight: Fraction | None  # pounds per piece
    each_weight_estimated: bool  # the each-weight is Kroger's estimate ("est.")
    product_id: str | None  # the product actually used, after any swap
    size: PackageSize | Unparseable | None  # that product's size (the item's own, if unlinked)
    unit_cents: int | None  # today's price per package or per pound
    regular_unit_cents: int | None  # the regular price per package or per pound
    cost_cents: int | None  # None when the line can't be priced, or is have-it
    regular_cents: int | None  # the same quantity at the regular price
    savings_cents: int
    price_fetched_at: datetime | None
    unconverted: tuple[Amount, ...]  # what couldn't be converted, summed by kind and unit
    used_by: tuple[MealUse, ...]  # ordered by meal id, so the order meals were added
    flags: frozenset[Flag]

    def __post_init__(self) -> None:
        object.__setattr__(self, "unit", PurchaseUnit(self.unit))
        for name in ("need", "computed", "quantity", "extra"):
            object.__setattr__(self, name, q(getattr(self, name)))
        for name in ("leftover", "leftover_count", "each_weight"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, q(value))
        for name in ("unit_cents", "regular_unit_cents", "cost_cents", "regular_cents"):
            _check_cents(getattr(self, name), name)
        _check_cents(self.savings_cents, "savings_cents")
        object.__setattr__(self, "unconverted", tuple(self.unconverted))
        object.__setattr__(self, "used_by", tuple(self.used_by))
        object.__setattr__(self, "flags", frozenset(self.flags))

    @property
    def have_it(self) -> bool:
        return Flag.HAVE_IT in self.flags


@dataclass(frozen=True, slots=True)
class ShoppingList:
    lines: tuple[Line, ...]  # sorted by (label.casefold(), key)
    totals: Totals

    def line(self, key: str) -> Line | None:
        return next((line for line in self.lines if line.key == key), None)


def build_list(plan: PlanInput, now: datetime) -> ShoppingList:
    """Merge every meal's amounts per item, round up once, and price each line (PLAN §8.4)."""
    require_aware(now)
    lines = [_item_line(plan, item_id, gathered, now) for item_id, gathered in _gather(plan)]
    lines.extend(_text_line(extra) for extra in plan.extras if extra.item_id is None)
    lines.sort(key=lambda line: (line.label.casefold(), line.key))
    return ShoppingList(tuple(lines), summarize(lines))


# ---- merging -------------------------------------------------------------------------------------


class _Gathered:
    """Everything the plan asks of one item."""

    __slots__ = ("amounts", "extra", "uses")

    def __init__(self) -> None:
        self.amounts: list[Amount] = []  # already scaled by the meal
        self.extra = _ZERO
        self.uses: dict[str, list[str]] = {}  # meal id -> dish names, in line order


def _gather(plan: PlanInput) -> list[tuple[str, _Gathered]]:
    gathered: dict[str, _Gathered] = {}
    for meal in plan.meals:
        for dish in meal.dishes:
            for dish_line in dish.lines:
                entry = gathered.setdefault(dish_line.item_id, _Gathered())
                entry.amounts.append(dish_line.amount.scaled(meal.scale))
                names = entry.uses.setdefault(meal.id, [])
                if dish.name not in names:
                    names.append(dish.name)
    for extra in plan.extras:
        if extra.item_id is not None:
            gathered.setdefault(extra.item_id, _Gathered()).extra += extra.quantity
    return list(gathered.items())


def _item_line(plan: PlanInput, item_id: str, gathered: _Gathered, now: datetime) -> Line:
    item = plan.items[item_id]
    own = plan.products.get(item_id)
    swap = plan.swaps.get(item_id)
    product = own if swap is None else swap
    flags: set[Flag] = set() if swap is None else {Flag.SWAPPED}

    parts = [contribution(a, item, product, own, swap is not None) for a in gathered.amounts]
    for part in parts:
        flags |= part.flags
    packages = sum((part.packages for part in parts), _ZERO)
    pounds = sum((part.lb for part in parts), _ZERO)
    pieces = sum((part.each for part in parts), _ZERO)
    unconverted = [part.unconverted for part in parts if part.unconverted is not None]
    each_lb, estimated = resolve_each_weight(item, product)
    by_weight = product is not None and product.sold_by is SoldBy.WEIGHT
    extra = gathered.extra

    # The line's unit, what the meals need, and what to buy for them (extras come on top).
    if product is None and {a.kind for a in gathered.amounts} == {AmountKind.COUNT}:
        unit, need, planned = PurchaseUnit.EACH, pieces, _ceil(pieces)  # unlinked, in pieces
    elif not by_weight:
        unit, need, planned = PurchaseUnit.PACKAGE, packages, _ceil(packages)
        if pieces:  # unlinked: pieces mixed with packages can't be added together
            unconverted.append(Amount(AmountKind.COUNT, pieces))
    elif pounds == 0 and extra == 0:
        unit, need, planned = PurchaseUnit.EACH, pieces, _ceil(pieces)  # priced via each-weight
    elif pieces and each_lb is None:
        unit, need = PurchaseUnit.POUND, pounds
        planned = ceil_to(pounds, _QUARTER_POUND)
        unconverted.append(Amount(AmountKind.COUNT, pieces))  # pieces of unknown weight
    else:
        weight = _ZERO if each_lb is None else each_lb
        unit, need = PurchaseUnit.POUND, pounds + pieces * weight
        planned = ceil_to(pounds, _QUARTER_POUND) + _ceil(pieces) * weight
    if by_weight and pieces and each_lb is None:
        flags.add(Flag.NEEDS_EACH_WEIGHT)
    weight_used = by_weight and each_lb is not None and (unit is PurchaseUnit.EACH or pieces > 0)
    at_least = bool(unconverted)
    if at_least:  # something unknown is still at least one step: a package, a piece, 1/4 lb
        floor = _STEP[unit]
        if unit is PurchaseUnit.POUND and each_lb is not None and each_lb > floor:
            floor = each_lb  # or one piece, so turning pieces into pounds never lowers the line
            weight_used = weight_used or planned < floor
        planned = max(planned, floor)

    computed = planned + extra
    quantity = computed
    override = plan.overrides.get(item_id)
    if override is not None and override.delta:
        delta: Fraction | None = None
        if override.unit is unit:
            delta = override.delta
        elif override.unit is PurchaseUnit.EACH and unit is PurchaseUnit.POUND and each_lb:
            delta = override.delta * each_lb  # set in pieces before the line turned to pounds
            weight_used = True
        if delta is None:
            flags.add(Flag.OVERRIDE_STALE)
        else:
            quantity = max(_ZERO, computed + delta)
            flags.add(Flag.OVERRIDDEN)
    if estimated and weight_used:
        flags.add(Flag.EST_EACH_WEIGHT)

    have_it = item_id in plan.have_it
    if have_it:
        flags.add(Flag.HAVE_IT)
    leftover = None if have_it or at_least else max(_ZERO, quantity - extra) - need
    if leftover is not None and leftover < 0:
        flags.add(Flag.SHORT)
    size = _size_used(item, product, own)
    leftover_count, leftover_measure = _leftover_parts(unit, leftover, size, each_lb)

    unit_cents = regular_unit_cents = cost = regular = None
    savings = 0
    fetched_at = None
    if product is None:
        flags.add(Flag.NO_PRODUCT)
    else:
        info = product.price
        regular_price = None if info is None else info.regular
        if info is None or not regular_price:
            flags.add(Flag.NO_PRICE)  # a promo alone is not trusted
        else:
            unit_cents = effective_cents(info, now)
            regular_unit_cents = regular_price
            fetched_at = info.fetched_at
            if promo_valid(info, now):
                flags.add(Flag.ON_SALE)
            if not have_it:
                cost = _line_cents(unit, quantity, each_lb, unit_cents)
                regular = _line_cents(unit, quantity, each_lb, regular_price)
                if cost is not None and regular is not None:
                    savings = regular - cost

    return Line(
        key=item_id,
        item_id=item_id,
        label=item.name,
        unit=unit,
        need=need,
        computed=computed,
        quantity=quantity,
        extra=extra,
        at_least=at_least,
        leftover=leftover,
        leftover_count=leftover_count,
        leftover_measure=leftover_measure,
        each_weight=each_lb,
        each_weight_estimated=estimated,
        product_id=None if product is None else product.product_id,
        size=size,
        unit_cents=unit_cents,
        regular_unit_cents=regular_unit_cents,
        cost_cents=cost,
        regular_cents=regular,
        savings_cents=savings,
        price_fetched_at=fetched_at,
        unconverted=_merge(unconverted),
        used_by=tuple(
            MealUse(meal_id, tuple(names)) for meal_id, names in sorted(gathered.uses.items())
        ),
        flags=frozenset(flags),
    )


def _text_line(extra: Extra) -> Line:
    """A plain-text extra ("birthday candles"): its own line, with no product or price."""
    return Line(
        key=f"extra:{extra.id}",
        item_id=None,
        label=extra.text or "",
        unit=PurchaseUnit.EACH,
        need=_ZERO,
        computed=extra.quantity,
        quantity=extra.quantity,
        extra=extra.quantity,
        at_least=False,
        leftover=_ZERO,
        leftover_count=None,
        leftover_measure=None,
        each_weight=None,
        each_weight_estimated=False,
        product_id=None,
        size=None,
        unit_cents=None,
        regular_unit_cents=None,
        cost_cents=None,
        regular_cents=None,
        savings_cents=0,
        price_fetched_at=None,
        unconverted=(),
        used_by=(),
        flags=frozenset({Flag.NO_PRODUCT}),
    )


def _ceil(x: Fraction) -> Fraction:
    return Fraction(math.ceil(x))


def _merge(amounts: Iterable[Amount]) -> tuple[Amount, ...]:
    """Sum amounts by kind and unit, in a fixed order, so input order never shows."""
    sums: dict[tuple[AmountKind, Unit | None], Fraction] = {}
    for a in amounts:
        sums[(a.kind, a.unit)] = sums.get((a.kind, a.unit), _ZERO) + a.value
    keys = sorted(
        sums, key=lambda k: (_KIND_ORDER[k[0]], -1 if k[1] is None else _UNIT_ORDER[k[1]])
    )
    return tuple(Amount(kind, sums[(kind, unit)], unit) for kind, unit in keys)


def _size_used(
    item: Item, product: Product | None, own: Product | None
) -> PackageSize | Unparseable | None:
    """The size of the product used: the household's applies only to the item's own product."""
    if product is None:
        return item.size_override
    if own is not None and own.product_id == product.product_id:
        return effective_size(item, product)
    return parse_size(product.size_text)


def _leftover_parts(
    unit: PurchaseUnit,
    leftover: Fraction | None,
    size: PackageSize | Unparseable | None,
    each_lb: Fraction | None,
) -> tuple[Fraction | None, Quantity | None]:
    """A positive leftover in pieces and as a weight or volume, where those are known."""
    if leftover is None or leftover <= 0:
        return None, None
    if unit is PurchaseUnit.POUND:
        return None, Quantity(leftover, Unit.LB)
    if unit is PurchaseUnit.EACH:
        return leftover, None if each_lb is None else Quantity(leftover * each_lb, Unit.LB)
    if not isinstance(size, PackageSize):
        return None, None
    count = None if size.count is None else leftover * size.count
    measure = (
        None if size.measure is None else Quantity(leftover * size.measure.value, size.measure.unit)
    )
    return count, measure


@dataclass(frozen=True, slots=True)
class LinePrice:
    """What a quantity costs today (a saved list bought again, priced afresh)."""

    unit_cents: int  # today's price per package or per pound
    cost_cents: int | None  # None for pieces whose weight isn't known
    regular_cents: int | None
    savings_cents: int
    on_sale: bool
    fetched_at: datetime


def price_quantity(
    unit: PurchaseUnit,
    quantity: Fraction,
    product: Product | None,
    each_lb: Fraction | None,
    now: datetime,
) -> LinePrice | None:
    """Price ``quantity`` (already whole packages, pieces or pounds) as the list does: whole
    packages exactly, pounds rounded half-up once, pieces through one piece's weight. None
    without a product or a regular price (a promo alone is not trusted)."""
    require_aware(now)
    info = None if product is None else product.price
    if info is None or not info.regular:
        return None
    unit_cents = effective_cents(info, now)
    cost = _line_cents(unit, q(quantity), each_lb, unit_cents)
    regular = _line_cents(unit, q(quantity), each_lb, info.regular)
    savings = 0 if cost is None or regular is None else regular - cost
    return LinePrice(unit_cents, cost, regular, savings, promo_valid(info, now), info.fetched_at)


def _line_cents(
    unit: PurchaseUnit, quantity: Fraction, each_lb: Fraction | None, cents: int
) -> int | None:
    """A line's cost at ``cents`` per package or per pound (PLAN §8.4 "Pricing a line")."""
    if unit is PurchaseUnit.PACKAGE:
        exact = quantity * cents  # whole packages times whole cents: no rounding
        return exact.numerator if exact.denominator == 1 else round_half_up(exact)
    if unit is PurchaseUnit.EACH:
        if each_lb is None:
            return None  # priced only once one piece's weight is known
        quantity *= each_lb
    return round_half_up(quantity * cents)


def _check_cents(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be whole cents (an int)")
    if value < 0:
        raise ValueError(f"{name} can't be negative")


# ---- words for the screens -----------------------------------------------------------------------


def quantity_text(line: Line, size: PackageSize | Unparseable | None) -> str:
    """The quantity in plain words: "2 boxes", "1 package", "3", "1 3/4 lb", "at least 1 package".

    ``size`` is the size of the product used (``line.size``).
    """
    words = quantity_words(line.unit, line.quantity, size)
    return f"at least {words}" if line.at_least else words


def quantity_words(
    unit: PurchaseUnit, quantity: Fraction, size: PackageSize | Unparseable | None
) -> str:
    """A quantity in a purchase unit, in plain words: "2 boxes", "1 package", "3", "1 3/4 lb".

    For anything with a quantity but no ``Line``, such as an extra. The noun is the size's
    container when it names the package ("3 lb bag"), else "package"; pieces, and things sold
    one at a time ("each"), are a bare number. ``size`` is the size of the product used.
    """
    number = to_mixed(q(quantity))
    if unit is PurchaseUnit.POUND:
        return f"{number} lb"
    sold_singly = isinstance(size, PackageSize) and size.measure is None and size.count == 1
    if unit is PurchaseUnit.EACH or sold_singly:
        return number  # pieces, or something sold one at a time ("each")
    noun = Container.PACKAGE
    if isinstance(size, PackageSize) and size.container is not None:
        if size.count is None or size.measure is None:  # in a multipack it names each piece
            noun = size.container
    return f"{number} {noun.value if 0 < quantity <= 1 else noun.plural}"


@dataclass(frozen=True, slots=True)
class UnitPrice:
    """Today's price per oz, fl oz, piece or lb, for comparing products when swapping."""

    cents: Fraction  # exact
    unit: Unit  # OZ, FL_OZ, EACH or LB
    text: str  # "$0.25 per oz", "$0.055 per fl oz", "$0.42 each", "$1.49 per lb"

    def __post_init__(self) -> None:
        object.__setattr__(self, "cents", q(self.cents))
        object.__setattr__(self, "unit", Unit(self.unit))


def unit_price(product: Product, now: datetime) -> UnitPrice | None:
    """The product's effective price per oz (weights), fl oz (volumes), piece (counts) or lb
    (sold by weight). None when it has no price, or its size can't be read."""
    info = product.price
    if info is None or not info.regular:
        return None
    cents = Fraction(effective_cents(info, now))
    if product.sold_by is SoldBy.WEIGHT:
        return UnitPrice(cents, Unit.LB, f"{_unit_money(cents)} per lb")
    size = parse_size(product.size_text)
    if isinstance(size, Unparseable):
        return None
    if size.measure is not None:
        by_weight = size.measure.dimension is Dimension.MASS
        per = Unit.OZ if by_weight else Unit.FL_OZ
        each = cents / convert(size.measure, per).value
        return UnitPrice(each, per, f"{_unit_money(each)} per {'oz' if by_weight else 'fl oz'}")
    count = cast(Fraction, size.count)  # a size has a count, a measure or both
    return UnitPrice(cents / count, Unit.EACH, f"{_unit_money(cents / count)} each")


def _unit_money(cents: Fraction) -> str:
    """Dollars to the cent ("$0.25"), or to a tenth of a cent under 10 cents ("$0.055")."""
    if cents < 10:
        tenths = round_half_up(cents * 10)
        return f"${tenths // 1000}.{tenths % 1000:03d}"
    whole = round_half_up(cents)
    return f"${whole // 100}.{whole % 100:02d}"
