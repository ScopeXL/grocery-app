"""Property tests (PLAN §8.6): 1 to 14, the picker promise, and a naive cross-check."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from typing import Any

import pytest
from hypothesis import assume, given, settings
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
from dinnerbell.domain.listbuild import UnitPrice, build_list, quantity_words
from dinnerbell.domain.models import (
    Amount,
    AmountKind,
    Dish,
    Extra,
    Flag,
    InvalidAmount,
    Item,
    Meal,
    PlanInput,
    Product,
    PurchaseUnit,
    QuantityOverride,
)
from dinnerbell.domain.money import (
    PriceInfo,
    about_dollars,
    dollars_to_cents,
    dollars_to_exact_cents,
    effective_cents,
    promo_valid,
)
from dinnerbell.domain.rational import ceil_to, q, round_half_up, to_text
from dinnerbell.domain.recommend import (
    Candidate,
    Recommendation,
    marginal_cost,
    meal_for,
    recommend,
)
from dinnerbell.domain.sizes import PackageSize, Unparseable, format_size, parse_size
from dinnerbell.domain.totals import Totals
from dinnerbell.domain.units import DimensionMismatch, Quantity, Unit, convert
from tests.domain.builders import NOW, dish, meal, offered_amounts, packages, plan_input, product
from tests.domain.strategies import (
    ITEM_IDS,
    amounts,
    candidate_dishes,
    items,
    new_meals,
    package_sizes,
    plans,
    positive_fractions,
    prices,
    products,
    quantities,
    recommendation_cases,
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

BASE_PLAN = plan_input(
    [meal("meal-1", dish("Tacos", ("cheese", packages("1/2"))))],
    {"cheese": (Item("cheese", "Sample Shredded Cheddar"), product("16 oz"))},
)
BASE_LINE = build_list(BASE_PLAN, NOW).lines[0]

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
    "Meal.scale": lambda f: Meal("meal-1", Dish("dish-1", "Tacos"), (), f),
    "QuantityOverride.delta": lambda f: QuantityOverride(f, PurchaseUnit.PACKAGE),
    "Extra.quantity": lambda f: Extra("extra-1", None, "birthday candles", f),
    "Totals": lambda f: Totals(f, 0, 0, 0, 0, 0, None),
    "UnitPrice": lambda f: UnitPrice(f, Unit.OZ, "$0.25 per oz"),
    "Line.quantity": lambda f: replace(BASE_LINE, quantity=f),
    "Line.cost_cents": lambda f: replace(BASE_LINE, cost_cents=f),
    "quantity_words": lambda f: quantity_words(PurchaseUnit.POUND, f, None),
    "Candidate.last_made": lambda f: Candidate(Dish("dish-1", "Tacos"), "main", last_made=f),
    "Recommendation": lambda f: Recommendation("dish-1", "Tacos", f, 0, 100, ("Cheese",), 0, ""),
    "recommend(limit)": lambda f: recommend(BASE_PLAN, [], NOW, limit=f),
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


# ---- 3: rounding never under-buys ----------------------------------------------------------------


@settings(max_examples=150)
@given(plans(adjust=False))
def test_3_rounding_never_under_buys(plan: PlanInput) -> None:
    for line in build_list(plan, NOW).lines:
        assert line.quantity == line.computed  # no override
        planned = line.computed - line.extra
        assert planned >= line.need
        if not line.at_least:  # less than one step over: a package, a piece, or 1/4 lb (+ a piece)
            step = Fraction(1)
            if line.unit is PurchaseUnit.POUND:
                step = Fraction(1, 4) + (line.each_weight or 0)
            assert planned - line.need < step, line


# ---- 4: merging is order-independent -------------------------------------------------------------


def _shuffled(plan: PlanInput, rnd: random.Random) -> PlanInput:
    def lines_shuffled(d: Dish) -> Dish:
        return Dish(d.id, d.name, tuple(rnd.sample(d.lines, len(d.lines))))

    meals = [
        Meal(m.id, lines_shuffled(m.main), tuple(lines_shuffled(s) for s in m.sides), m.scale)
        for m in rnd.sample(plan.meals, len(plan.meals))
    ]
    return replace(
        plan, meals=tuple(meals), extras=tuple(rnd.sample(plan.extras, len(plan.extras)))
    )


@settings(max_examples=100)
@given(plans(), st.randoms(use_true_random=False))
def test_4_merging_is_order_independent(plan: PlanInput, rnd: random.Random) -> None:
    assert build_list(_shuffled(plan, rnd), NOW) == build_list(plan, NOW)


# ---- 5: merged packages are between the largest single meal and the sum of meals -----------------


@settings(max_examples=200)
@given(plans(unit_sold_only=True, extras=False, have_it=False, adjust=False))
def test_5_merging_buys_no_more_than_meal_by_meal(plan: PlanInput) -> None:
    whole = build_list(plan, NOW)
    singles = [build_list(replace(plan, meals=(m,)), NOW) for m in plan.meals]
    for line in whole.lines:
        alone = [single.line(line.key) for single in singles]
        each = [Fraction(0) if one is None else one.quantity for one in alone]
        assert max(each) <= line.quantity <= sum(each)


# ---- 6 and 7: adding a meal never lowers a line, the total or the tally --------------------------


def _without_negative_pound_overrides(plan: PlanInput) -> PlanInput:
    """A pound override that went stale on a pieces line comes back when the line turns to pounds
    again; a negative one then lowers it, by the household's own choice. Keep those out."""
    kept = {
        item_id: override
        for item_id, override in plan.overrides.items()
        if not (override.unit is PurchaseUnit.POUND and override.delta < 0)
    }
    return replace(plan, overrides=kept)


@settings(max_examples=150)
@given(plans(), new_meals())
def test_6_adding_a_meal_never_lowers_anything(plan: PlanInput, more: Meal) -> None:
    plan = _without_negative_pound_overrides(plan)
    before, after = build_list(plan, NOW), build_list(plan.with_meal(more), NOW)
    for line in before.lines:
        later = after.line(line.key)
        assert later is not None
        if later.unit is line.unit:  # a pieces line can turn to pounds
            assert later.quantity >= line.quantity, (line, later)
        elif line.each_weight is not None and later.unit is PurchaseUnit.POUND:
            assert later.quantity >= line.quantity * line.each_weight
    assert after.totals.total >= before.totals.total
    assert after.totals.not_priced >= before.totals.not_priced


def _total(plan: PlanInput) -> int:
    return build_list(plan, NOW).totals.total


@settings(max_examples=100)
@given(plans(), candidate_dishes())
def test_7_marginal_cost_is_what_the_dish_adds(plan: PlanInput, d: Dish) -> None:
    plan = _without_negative_pound_overrides(plan)
    added, unpriced = marginal_cost(plan, d, NOW)
    assert 0 <= added == _total(plan.with_meal(meal_for(d))) - _total(plan)
    assert unpriced >= 0


@settings(max_examples=100)
@given(plans(), candidate_dishes())
def test_7_marginal_cost_is_never_below_zero(plan: PlanInput, d: Dish) -> None:
    added, _ = marginal_cost(plan, d, NOW)  # any overrides: a negative difference is clamped
    assert added == max(0, _total(plan.with_meal(meal_for(d))) - _total(plan))


# ---- 8: need scales with the meal ----------------------------------------------------------------


@settings(max_examples=100)
@given(plans())
def test_8_need_doubles_when_every_meal_doubles(plan: PlanInput) -> None:
    def at(scale: Fraction) -> PlanInput:
        return replace(plan, meals=tuple(replace(m, scale=scale) for m in plan.meals))

    once, twice = build_list(at(Fraction(1)), NOW), build_list(at(Fraction(2)), NOW)
    for line in once.lines:
        doubled = twice.line(line.key)
        assert doubled is not None
        assert doubled.need == 2 * line.need
        assert doubled.unconverted == tuple(a.scaled(Fraction(2)) for a in line.unconverted)


@given(amounts())
def test_8_scaling_there_and_back_is_exact(a: Amount) -> None:
    assert a.scaled(Fraction(2)).scaled(Fraction(1, 2)) == a.scaled(Fraction(1))


# ---- 9: totals add up ----------------------------------------------------------------------------


@settings(max_examples=100)
@given(plans())
def test_9_totals_add_up(plan: PlanInput) -> None:
    totals = build_list(plan, NOW).totals
    assert totals.total >= 0 and totals.savings >= 0
    assert totals.total + totals.savings == totals.regular_total


@settings(max_examples=100)
@given(plans(), st.sampled_from(ITEM_IDS))
def test_9_marking_have_it_never_raises_the_total(plan: PlanInput, item_id: str) -> None:
    marked = replace(plan, have_it=plan.have_it | {item_id})
    assert build_list(marked, NOW).totals.total <= build_list(plan, NOW).totals.total


def _repriced(plan: PlanInput, change: Callable[[PriceInfo], PriceInfo]) -> PlanInput:
    def reprice(p: Product) -> Product:
        return p if p.price is None else replace(p, price=change(p.price))

    return replace(
        plan,
        products={k: None if p is None else reprice(p) for k, p in plan.products.items()},
        swaps={k: reprice(p) for k, p in plan.swaps.items()},
    )


@settings(max_examples=100)
@given(plans(), st.integers(min_value=1, max_value=500))
def test_9_raising_regular_prices_never_lowers_the_total(plan: PlanInput, more: int) -> None:
    # Kroger's per-each estimate is a price too: holding it while the pound price rises would
    # shrink the each-weight it implies, so these plans weigh pieces only by household values.
    plan = _repriced(plan, lambda p: replace(p, each_estimate=None))
    raised = _repriced(plan, lambda p: replace(p, regular=p.regular + more) if p.regular else p)
    assert build_list(raised, NOW).totals.total >= build_list(plan, NOW).totals.total


# ---- 10: the effective price ---------------------------------------------------------------------


@given(prices())
def test_10_the_promo_is_used_exactly_when_it_is_valid(price: PriceInfo) -> None:
    assume(bool(price.regular))
    effective = effective_cents(price, NOW)
    assert price.regular is not None and effective <= price.regular
    assert effective == (price.promo if promo_valid(price, NOW) else price.regular)


# ---- 11: no-op swaps and deltas ------------------------------------------------------------------


@settings(max_examples=100)
@given(plans(swaps=False), st.sampled_from(ITEM_IDS))
def test_11_swapping_to_the_same_product_only_adds_swapped(plan: PlanInput, item_id: str) -> None:
    own = plan.products.get(item_id)
    assume(own is not None)
    assert own is not None
    before = build_list(plan, NOW)
    after = build_list(replace(plan, swaps={item_id: own}), NOW)
    assert after.totals == before.totals
    for old, new in zip(before.lines, after.lines, strict=True):
        expected = replace(old, flags=old.flags | {Flag.SWAPPED}) if old.key == item_id else old
        assert new == expected


@settings(max_examples=100)
@given(plans(adjust=False), st.sampled_from(ITEM_IDS), st.sampled_from(tuple(PurchaseUnit)))
def test_11_a_zero_delta_is_a_no_op(plan: PlanInput, item_id: str, unit: PurchaseUnit) -> None:
    zero = replace(plan, overrides={item_id: QuantityOverride(Fraction(0), unit)})
    assert build_list(zero, NOW) == build_list(plan, NOW)


# ---- 12: rounding half-up is never off by more than a half ---------------------------------------


@given(st.fractions(min_value=Fraction(0), max_denominator=64))
def test_12_round_half_up_is_within_a_half(x: Fraction) -> None:
    assert abs(round_half_up(x) - x) <= Fraction(1, 2)


# ---- a deliberately naive reference for unit-sold plans (PLAN §8.6) ------------------------------

_OZ_IN_G = Fraction("28.349523125")
_FL_OZ_IN_ML = Fraction("29.5735295625")
_GRAMS = {Unit.G: Fraction(1), Unit.KG: Fraction(1000), Unit.OZ: _OZ_IN_G, Unit.LB: 16 * _OZ_IN_G}
_ML = {
    Unit.ML: Fraction(1),
    Unit.L: Fraction(1000),
    Unit.FL_OZ: _FL_OZ_IN_ML,
    Unit.TSP: _FL_OZ_IN_ML / 6,
    Unit.TBSP: _FL_OZ_IN_ML / 2,
    Unit.CUP: 8 * _FL_OZ_IN_ML,
    Unit.PT: 16 * _FL_OZ_IN_ML,
    Unit.QT: 32 * _FL_OZ_IN_ML,
    Unit.GAL: 128 * _FL_OZ_IN_ML,
}


def _naive_need(plan: PlanInput, item_id: str, size: PackageSize) -> Fraction:
    """Packages needed, the slow and obvious way: every line, straight from the unit table."""
    total = Fraction(0)
    for m in plan.meals:
        for d in m.dishes:
            for dish_line in d.lines:
                if dish_line.item_id != item_id:
                    continue
                a, value = dish_line.amount, dish_line.amount.value * m.scale
                if a.kind is AmountKind.PACKAGES:
                    total += value
                elif a.kind is AmountKind.COUNT:
                    assert size.count is not None
                    total += value / size.count
                else:
                    assert a.unit is not None and size.measure is not None
                    table = _GRAMS if a.unit in _GRAMS else _ML
                    total += value * table[a.unit] / (size.measure.value * table[size.measure.unit])
    return total


@settings(max_examples=300)
@given(plans(unit_sold_only=True, adjust=False))
def test_the_list_agrees_with_a_naive_reference(plan: PlanInput) -> None:
    shopping = build_list(plan, NOW)
    expected_total = 0
    for item_id, own in plan.products.items():
        assert own is not None and own.price is not None and own.price.regular is not None
        size = parse_size(own.size_text)
        assert isinstance(size, PackageSize)
        need = _naive_need(plan, item_id, size)
        extra = sum((e.quantity for e in plan.extras if e.item_id == item_id), Fraction(0))
        used = extra > 0 or any(
            dish_line.item_id == item_id
            for m in plan.meals
            for d in m.dishes
            for dish_line in d.lines
        )
        line = shopping.line(item_id)
        if not used:
            assert line is None
            continue
        assert line is not None
        buy = math.ceil(need) + extra
        assert (line.need, line.quantity) == (need, buy)
        regular, promo = own.price.regular, own.price.promo
        each = promo if promo is not None and 0 < promo < regular else regular
        cost = None if item_id in plan.have_it else int(buy * each)
        assert line.cost_cents == cost
        expected_total += cost or 0
    assert shopping.totals.total == expected_total


# ---- 13: recommendations -------------------------------------------------------------------------


@settings(max_examples=150)
@given(recommendation_cases(), st.integers(min_value=0, max_value=4), st.randoms())
def test_13_recommendations_are_deterministic_limited_and_worth_naming(
    case: tuple[PlanInput, list[Candidate]], limit: int, rnd: random.Random
) -> None:
    plan, candidates = case
    pool = [*candidates, *(Candidate(m.main, "main") for m in plan.meals)]  # planned: left out
    found = recommend(plan, pool, NOW, limit=limit)
    assert recommend(plan, rnd.sample(pool, len(pool)), NOW, limit=limit) == found
    assert len(found) <= limit
    left_out = {c.dish.id for c in pool if c.role != "main" or c.archived}
    left_out |= {m.main.id for m in plan.meals}
    for r in found:
        assert r.named and r.value_cents >= 100
        assert r.dish_id not in left_out
        assert r.text.startswith(f"{r.name} uses your leftover ")
