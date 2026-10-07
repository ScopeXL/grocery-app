"""listbuild.py: merge, round and price (PLAN §8.4), case by case from the §8.5 tables.

All data is synthetic. Every case uses ``NOW`` (2026-10-06T14:00Z).
"""

from __future__ import annotations

import math
import random
from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction
from typing import Any, cast

import pytest

from dinnerbell.domain.listbuild import (
    Line,
    MealUse,
    UnitPrice,
    build_list,
    price_quantity,
    quantity_text,
    quantity_words,
    unit_price,
)
from dinnerbell.domain.models import (
    Dish,
    Extra,
    Flag,
    Item,
    Meal,
    PlanInput,
    Product,
    PurchaseUnit,
    QuantityOverride,
)
from dinnerbell.domain.money import dollars_to_exact_cents
from dinnerbell.domain.sizes import PackageSize, parse_size
from dinnerbell.domain.units import Quantity, Unit
from tests.domain.builders import (
    NOW,
    Stock,
    by_weight,
    count,
    dish,
    line_for,
    meal,
    measure,
    packages,
    plan_input,
    product,
)

CHEESE = Item("cheese", "Sample Shredded Cheddar")
ONIONS = Item("onions", "Sample Yellow Onions", each_weight=Fraction(1, 2))  # 8 oz each
ONIONS_UNWEIGHED = Item("onions", "Sample Yellow Onions")
BEEF = Item("beef", "Sample Ground Beef")
BEANS = Item("beans", "Sample Black Beans")


def one_line(plan: PlanInput) -> Line:
    lines = build_list(plan, NOW).lines
    assert len(lines) == 1, lines
    return lines[0]


def cheese(*meals: Meal, size: str = "16 oz") -> PlanInput:
    return plan_input(meals, {"cheese": (CHEESE, product(size))})


# ---- M: merge and round ------------------------------------------------------------------------


def test_m1_shares_merge_across_meals_before_rounding() -> None:
    line = one_line(
        cheese(
            meal("meal-1", dish("Tacos", ("cheese", packages("1/4")))),
            meal("meal-2", dish("Nachos", ("cheese", packages("1/4")))),
            meal("meal-3", dish("Quesadillas", ("cheese", packages("1/2")))),
        )
    )
    assert (line.need, line.quantity, line.leftover) == (1, 1, 0)
    assert line.unit is PurchaseUnit.PACKAGE


def test_m2_exact_shares_never_buy_an_extra_package() -> None:
    meals = [
        meal(f"meal-{n}", dish(f"Dish {n}", ("cheese", measure("1.1", Unit.OZ)))) for n in "123"
    ]
    line = one_line(cheese(*meals, size="3.3 oz"))
    assert (line.need, line.quantity) == (1, 1)
    assert math.ceil((1.1 + 1.1 + 1.1) / 3.3) == 2  # what floats would buy


def test_m3_a_main_and_side_in_one_meal_are_one_use() -> None:
    line = one_line(
        cheese(
            meal(
                "meal-1",
                dish("Tacos", ("cheese", packages("1/2"))),
                dish("Rice", ("cheese", packages("1/2"))),
            )
        )
    )
    assert line.quantity == 1
    assert line.used_by == (MealUse("meal-1", ("Tacos", "Rice")),)


def test_m4_the_same_item_twice_in_one_dish() -> None:
    line = one_line(
        cheese(
            meal("meal-1", dish("Tacos", ("cheese", packages("1/4")), ("cheese", packages("1/2"))))
        )
    )
    assert (line.quantity, line.leftover) == (1, Fraction(1, 4))
    assert line.used_by == (MealUse("meal-1", ("Tacos",)),)


def test_m5_half_a_meal_still_buys_a_whole_avocado() -> None:
    avocado = Item("avocado", "Sample Avocado")
    toast = meal("meal-1", dish("Avocado toast", ("avocado", count("1"))), scale="1/2")
    line = one_line(plan_input([toast], {"avocado": (avocado, product("1 each"))}))
    assert (line.quantity, line.leftover, line.leftover_count) == (
        1,
        Fraction(1, 2),
        Fraction(1, 2),
    )
    assert quantity_text(line, line.size) == "1"


def test_m6_half_of_three_quarters() -> None:
    line = one_line(cheese(meal("meal-1", dish("Tacos", ("cheese", packages("3/4"))), scale="1/2")))
    assert (line.need, line.quantity) == (Fraction(3, 8), 1)


def test_m7_scaled_weights_merge_and_the_leftover_reads_in_ounces() -> None:
    line = one_line(
        cheese(
            meal("meal-1", dish("Tacos", ("cheese", measure("6", Unit.OZ))), scale="2"),
            meal("meal-2", dish("Nachos", ("cheese", measure("6", Unit.OZ)))),
        )
    )
    assert (line.need, line.quantity, line.leftover) == (Fraction(9, 8), 2, Fraction(7, 8))
    assert line.leftover_measure == Quantity(Fraction(14), Unit.OZ)


def test_m8_order_never_matters() -> None:
    stock: Stock = {
        "cheese": (CHEESE, product("16 oz")),
        "onions": (ONIONS, by_weight(149, product_id="0000000000002")),
    }
    lines = [("cheese", packages("1/4")), ("onions", count("2")), ("cheese", measure("2", Unit.OZ))]
    meals = [
        meal("meal-1", dish("Tacos", *lines)),
        meal("meal-2", dish("Nachos", ("cheese", packages("1/4"))), dish("Salsa", *lines[1:])),
        meal("meal-3", dish("Quesadillas", ("cheese", packages("1/2")))),
    ]
    shuffle = random.Random(8)

    def shuffled(m: Meal) -> Meal:
        dishes = [
            Dish(d.id, d.name, tuple(shuffle.sample(d.lines, len(d.lines)))) for d in m.dishes
        ]
        return Meal(m.id, dishes[0], tuple(dishes[1:]), m.scale)

    reordered = [shuffled(m) for m in reversed(meals)]
    assert build_list(plan_input(reordered, stock), NOW) == build_list(
        plan_input(meals, stock), NOW
    )


# ---- W: sold by weight -------------------------------------------------------------------------


def test_w1_weights_round_up_to_quarter_pounds() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Chili", ("beef", measure("21", Unit.OZ))))],
        {"beef": (BEEF, by_weight(549))},
    )
    line = one_line(plan)
    assert (line.unit, line.need, line.quantity) == (
        PurchaseUnit.POUND,
        Fraction(21, 16),
        Fraction(3, 2),
    )
    assert line.cost_cents == 824
    assert quantity_text(line, line.size) == "1 1/2 lb"


def test_w2_a_weight_line_rounds_its_price_half_up_once() -> None:
    thighs = Item("thighs", "Sample Chicken Thighs")
    plan = plan_input(
        [meal("meal-1", dish("Curry", ("thighs", measure("1.5", Unit.LB))))],
        {"thighs": (thighs, by_weight(299))},
    )
    assert one_line(plan).cost_cents == 449  # 448.5


def test_w3_pieces_are_priced_through_the_each_weight() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Chili", ("onions", count("3"))))],
        {"onions": (ONIONS, by_weight(149))},
    )
    line = one_line(plan)
    assert (line.unit, line.quantity, line.each_weight) == (PurchaseUnit.EACH, 3, Fraction(1, 2))
    assert line.cost_cents == 224  # 1 1/2 lb


def test_w4_a_sane_kroger_estimate_prices_the_pieces() -> None:
    onions = by_weight(149, promo=129, each_estimate=Fraction(75))
    plan = plan_input(
        [meal("meal-1", dish("Chili", ("onions", count("3"))))],
        {"onions": (ONIONS_UNWEIGHED, onions)},
    )
    shopping = build_list(plan, NOW)
    line = shopping.lines[0]
    assert (line.each_weight, line.each_weight_estimated) == (Fraction(75, 149), True)
    assert (line.cost_cents, line.regular_cents, line.savings_cents) == (195, 225, 30)
    assert {Flag.EST_EACH_WEIGHT, Flag.ON_SALE} <= line.flags
    assert shopping.totals.savings == 30


def test_w5_an_insane_estimate_leaves_the_pieces_unpriced() -> None:
    onions = by_weight(219, each_estimate=dollars_to_exact_cents("0.0995"))
    plan = plan_input(
        [meal("meal-1", dish("Chili", ("onions", count("3"))))],
        {"onions": (ONIONS_UNWEIGHED, onions)},
    )
    shopping = build_list(plan, NOW)
    line = shopping.lines[0]
    assert (line.unit, line.quantity, line.cost_cents) == (PurchaseUnit.EACH, 3, None)
    assert line.each_weight is None
    assert Flag.NEEDS_EACH_WEIGHT in line.flags
    assert quantity_text(line, line.size) == "3"  # "3 onions", no price
    assert shopping.totals.not_priced == 1


def test_w6_an_estimate_equal_to_the_pound_price_is_ignored() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Chili", ("onions", count("3"))))],
        {"onions": (ONIONS_UNWEIGHED, by_weight(149, each_estimate=Fraction(149)))},
    )
    line = one_line(plan)
    assert (line.each_weight, line.cost_cents) == (None, None)


def test_w7_pieces_and_weight_add_up_in_pounds() -> None:
    plan = plan_input(
        [
            meal("meal-1", dish("Fajitas", ("onions", count("5"))), scale="1/2"),
            meal("meal-2", dish("Soup", ("onions", measure("4", Unit.OZ)))),
        ],
        {"onions": (ONIONS, by_weight(149))},
    )
    line = one_line(plan)
    assert (line.unit, line.need, line.quantity) == (
        PurchaseUnit.POUND,
        Fraction(3, 2),
        Fraction(7, 4),
    )
    assert line.leftover == Fraction(1, 4)
    assert line.leftover_measure == Quantity(Fraction(1, 4), Unit.LB)
    assert quantity_text(line, line.size) == "1 3/4 lb"


def test_w8_a_volume_of_something_sold_by_weight_stays_visible() -> None:
    cup = measure("1", Unit.CUP)
    plan = plan_input(
        [meal("meal-1", dish("Soup", ("onions", cup)))],
        {"onions": (ONIONS_UNWEIGHED, by_weight(149))},
    )
    shopping = build_list(plan, NOW)
    line = shopping.lines[0]
    assert line.unconverted == (cup,)
    assert Flag.NOT_CONVERTIBLE in line.flags
    assert (line.at_least, line.quantity) == (True, 1)  # at least one piece
    assert shopping.totals.not_priced == 1


# ---- P: pricing a line ---------------------------------------------------------------------------


def beans(
    regular: int | None = 349,
    promo: int | None = None,
    *,
    promo_from: datetime | None = None,
    promo_until: datetime | None = None,
    priced: bool = True,
) -> PlanInput:
    can = product(
        "15 oz can",
        regular=regular,
        promo=promo,
        promo_from=promo_from,
        promo_until=promo_until,
        priced=priced,
    )
    return plan_input(
        [meal("meal-1", dish("Chili", ("beans", packages("2"))))], {"beans": (BEANS, can)}
    )


def test_p1_a_valid_promo_is_the_price() -> None:
    line = one_line(beans(promo=299))
    assert (line.cost_cents, line.regular_cents, line.savings_cents) == (598, 698, 100)
    assert (line.unit_cents, line.regular_unit_cents) == (299, 349)
    assert Flag.ON_SALE in line.flags


def test_p2_an_ended_promo_is_ignored() -> None:
    line = one_line(beans(promo=299, promo_until=datetime(2026, 10, 5, 4, 0, tzinfo=UTC)))
    assert (line.cost_cents, line.savings_cents) == (698, 0)
    assert Flag.ON_SALE not in line.flags


def test_p3_a_promo_ends_at_its_end_instant() -> None:
    assert one_line(beans(promo=299, promo_until=NOW)).cost_cents == 698


def test_p4_a_promo_that_has_not_started_is_ignored() -> None:
    line = one_line(beans(promo=299, promo_from=datetime(2026, 10, 7, tzinfo=UTC)))
    assert line.cost_cents == 698


@pytest.mark.parametrize("promo", [349, 400, 0, None])
def test_p5_a_promo_counts_only_below_the_regular_price(promo: int | None) -> None:
    line = one_line(beans(promo=promo))
    assert (line.cost_cents, line.savings_cents) == (698, 0)


@pytest.mark.parametrize(
    "plan",
    [beans(regular=0), beans(regular=None), beans(priced=False)],
    ids=["regular 0", "regular null", "not sold at the store"],
)
def test_p6_no_regular_price_means_no_price(plan: PlanInput) -> None:
    shopping = build_list(plan, NOW)
    line = shopping.lines[0]
    assert Flag.NO_PRICE in line.flags
    assert (line.cost_cents, line.quantity) == (None, 2)
    assert (shopping.totals.total, shopping.totals.not_priced) == (0, 1)


def test_p7_a_promo_alone_is_not_a_price() -> None:
    line = one_line(beans(regular=None, promo=299))
    assert Flag.NO_PRICE in line.flags
    assert line.cost_cents is None


# ---- L: lines, extras, overrides and swaps ------------------------------------------------------


def test_l1_an_unlinked_item_is_listed_without_a_price() -> None:
    eggs = Item("eggs", "Sample Farm Eggs")
    plan = plan_input(
        [meal("meal-1", dish("Omelet", ("eggs", packages("1"))))], {"eggs": (eggs, None)}
    )
    shopping = build_list(plan, NOW)
    line = shopping.lines[0]
    assert Flag.NO_PRODUCT in line.flags
    assert (line.unit, line.quantity, line.cost_cents) == (PurchaseUnit.PACKAGE, 1, None)
    assert shopping.totals.not_priced == 1


def test_l2_have_it_is_listed_but_not_bought() -> None:
    oil = Item("oil", "Sample Olive Oil")
    plan = plan_input(
        [meal("meal-1", dish("Salad", ("oil", measure("2", Unit.TBSP))))],
        {"oil": (oil, product("16.9 fl oz", regular=499))},
        have_it={"oil"},
    )
    shopping = build_list(plan, NOW)
    line = shopping.lines[0]
    assert Flag.HAVE_IT in line.flags and line.have_it
    assert (line.quantity, line.cost_cents, line.leftover) == (1, None, None)
    assert (shopping.totals.total, shopping.totals.not_priced, shopping.totals.have_it) == (0, 0, 1)


def test_l3_a_plain_text_extra_is_its_own_line() -> None:
    candles = Extra("extra-1", None, "birthday candles", Fraction(1))
    shopping = build_list(plan_input([], {}, extras=[candles]), NOW)
    line = line_for(shopping, "extra:extra-1")
    assert (line.label, line.item_id, line.quantity) == ("birthday candles", None, 1)
    assert line.flags == {Flag.NO_PRODUCT}
    assert quantity_text(line, line.size) == "1"
    assert shopping.totals.not_priced == 1


def test_l4_an_item_extra_on_its_own() -> None:
    milk = Item("milk", "Sample Whole Milk")
    plan = plan_input(
        [],
        {"milk": (milk, product("1/2 gal", regular=129))},
        extras=[Extra("extra-1", "milk", None, Fraction(2))],
    )
    shopping = build_list(plan, NOW)
    line = shopping.lines[0]
    assert (line.quantity, line.extra, line.need, line.cost_cents) == (2, 2, 0, 258)
    assert line.used_by == ()
    assert shopping.totals.total == 258


def test_l5_an_extra_is_never_counted_as_leftover() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", packages("3/4"))))],
        {"cheese": (CHEESE, product("16 oz"))},
        extras=[Extra("extra-1", "cheese", None, Fraction(1))],
    )
    line = one_line(plan)
    assert (line.computed, line.quantity, line.extra) == (2, 2, 1)
    assert line.leftover == Fraction(1, 4)


def test_l6_an_override_is_a_delta_that_rides_on_top() -> None:
    typed_three = {"cheese": QuantityOverride(Fraction(3 - 1), PurchaseUnit.PACKAGE)}
    before = one_line(cheese(meal("meal-1", dish("Tacos", ("cheese", packages("1"))))))
    assert before.computed == 1
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", packages("1"))))],
        {"cheese": (CHEESE, product("16 oz"))},
        overrides=typed_three,
    )
    assert one_line(plan).quantity == 3
    grown = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", packages("5/4"))))],
        {"cheese": (CHEESE, product("16 oz"))},
        overrides=typed_three,
    )
    line = one_line(grown)
    assert (line.computed, line.quantity) == (2, 4)
    assert Flag.OVERRIDDEN in line.flags


def test_l7_an_override_to_zero_is_short() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", packages("3/4"))))],
        {"cheese": (CHEESE, product("16 oz"))},
        overrides={"cheese": QuantityOverride(Fraction(-1), PurchaseUnit.PACKAGE)},
    )
    line = one_line(plan)
    assert (line.quantity, line.cost_cents, line.leftover) == (0, 0, Fraction(-3, 4))
    assert Flag.SHORT in line.flags


def test_l8_a_piece_override_with_no_weight_goes_stale_when_the_line_turns_to_pounds() -> None:
    plan = plan_input(
        [
            meal("meal-1", dish("Chili", ("onions", count("3")))),
            meal("meal-2", dish("Soup", ("onions", measure("4", Unit.OZ)))),
        ],
        {"onions": (ONIONS_UNWEIGHED, by_weight(149))},
        overrides={"onions": QuantityOverride(Fraction(2), PurchaseUnit.EACH)},
    )
    line = one_line(plan)
    assert line.unit is PurchaseUnit.POUND
    assert Flag.OVERRIDE_STALE in line.flags
    assert Flag.OVERRIDDEN not in line.flags
    assert line.quantity == line.computed  # ignored


def test_l9_a_weight_carries_over_to_a_swapped_bigger_package() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", measure("6", Unit.OZ))))],
        {"cheese": (CHEESE, product("8 oz", regular=250))},
        swaps={"cheese": product("2 lb", regular=899, product_id="0000000000002")},
    )
    line = one_line(plan)
    assert (line.need, line.quantity, line.cost_cents) == (Fraction(3, 16), 1, 899)
    assert line.leftover_measure == Quantity(Fraction(13, 8), Unit.LB)
    assert (line.product_id, Flag.SWAPPED in line.flags) == ("0000000000002", True)
    assert plan.meals[0].main.lines[0].amount == measure("6", Unit.OZ)  # the dish is unchanged


def test_l10_part_of_a_package_keeps_its_size_across_a_swap() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", packages("1/2"))))],
        {"cheese": (CHEESE, product("16 oz"))},
        swaps={"cheese": product("32 oz", regular=599, product_id="0000000000002")},
    )
    line = one_line(plan)
    assert (line.need, line.quantity, line.cost_cents) == (Fraction(1, 4), 1, 599)


def test_l11_an_unreadable_original_buys_the_same_share_and_asks_for_a_check() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", packages("1/2"))))],
        {"cheese": (CHEESE, product("Varies"))},
        swaps={"cheese": product("16 oz", product_id="0000000000002")},
    )
    shopping = build_list(plan, NOW)
    line = shopping.lines[0]
    assert (line.need, line.quantity) == (Fraction(1, 2), 1)
    assert Flag.APPROX_SWAP in line.flags
    assert shopping.totals.needs_check == 1


def test_l12_a_weight_swapped_to_a_count_keeps_the_share() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", measure("6", Unit.OZ))))],
        {"cheese": (CHEESE, product("16 oz"))},
        swaps={"cheese": product("6 ct", product_id="0000000000002")},
    )
    line = one_line(plan)
    assert (line.need, line.quantity) == (Fraction(3, 8), 1)
    assert Flag.APPROX_SWAP in line.flags


def test_l13_a_bag_swapped_to_loose_by_the_pound() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Chili", ("onions", packages("1/2"))))],
        {"onions": (ONIONS_UNWEIGHED, product("3 lb bag"))},
        swaps={"onions": by_weight(149, product_id="0000000000002")},
    )
    line = one_line(plan)
    assert (line.unit, line.quantity, line.cost_cents) == (PurchaseUnit.POUND, Fraction(3, 2), 224)


# ---- more of the algorithm -----------------------------------------------------------------------


def test_lines_are_sorted_by_name_then_key() -> None:
    stock: Stock = {
        "b": (Item("b", "salsa"), product("16 oz")),
        "a": (Item("a", "Salsa"), product("16 oz")),
        "c": (Item("c", "Avocado"), product("each")),
    }
    tacos = dish("Tacos", ("b", packages("1")), ("a", packages("1")), ("c", count("1")))
    keys = [line.key for line in build_list(plan_input([meal("meal-1", tacos)], stock), NOW).lines]
    assert keys == ["c", "a", "b"]


def test_used_by_is_ordered_by_meal_whatever_the_plan_order() -> None:
    plan = cheese(
        meal("meal-2", dish("Nachos", ("cheese", packages("1/4")))),
        meal("meal-1", dish("Tacos", ("cheese", packages("1/4")))),
    )
    assert [use.meal_id for use in one_line(plan).used_by] == ["meal-1", "meal-2"]


def test_an_unlinked_item_counted_in_pieces() -> None:
    lemons = Item("lemons", "Sample Lemons")
    plan = plan_input(
        [
            meal("meal-1", dish("Fish", ("lemons", count("1")))),
            meal("meal-2", dish("Tea", ("lemons", count("3/2")))),
        ],
        {"lemons": (lemons, None)},
    )
    line = one_line(plan)
    assert (line.unit, line.need, line.quantity, line.at_least) == (
        PurchaseUnit.EACH,
        Fraction(5, 2),
        3,
        False,
    )
    assert quantity_text(line, line.size) == "3"


def test_an_unlinked_item_with_mixed_amounts_is_at_least_one_package() -> None:
    lemons = Item("lemons", "Sample Lemons")
    plan = plan_input(
        [meal("meal-1", dish("Fish", ("lemons", count("2")), ("lemons", packages("1/2"))))],
        {"lemons": (lemons, None)},
    )
    line = one_line(plan)
    assert (line.unit, line.quantity, line.at_least) == (PurchaseUnit.PACKAGE, 1, True)
    assert line.unconverted == (count("2"),)
    assert quantity_text(line, line.size) == "at least 1 package"


def test_unconverted_amounts_are_summed_by_kind_and_unit() -> None:
    plan = cheese(
        meal("meal-1", dish("Tacos", ("cheese", measure("6", Unit.OZ)))),
        meal(
            "meal-2", dish("Nachos", ("cheese", measure("2", Unit.OZ)), ("cheese", packages("1/2")))
        ),
        size="Varies",
    )
    line = one_line(plan)
    assert line.unconverted == (measure("8", Unit.OZ),)  # "8 oz needed"
    assert (line.at_least, line.quantity, line.need) == (True, 1, Fraction(1, 2))
    assert Flag.SIZE_UNKNOWN in line.flags


def test_a_piece_override_counts_in_pounds_when_one_piece_weighs_a_known_amount() -> None:
    plan = plan_input(
        [
            meal("meal-1", dish("Chili", ("onions", count("3")))),
            meal("meal-2", dish("Soup", ("onions", measure("4", Unit.OZ)))),
        ],
        {"onions": (ONIONS, by_weight(149))},
        overrides={"onions": QuantityOverride(Fraction(2), PurchaseUnit.EACH)},
    )
    line = one_line(plan)
    assert (line.computed, line.quantity) == (Fraction(7, 4), Fraction(11, 4))  # + 2 x 1/2 lb
    assert Flag.OVERRIDDEN in line.flags


def test_an_override_in_another_unit_is_stale() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Chili", ("beef", measure("1", Unit.LB))))],
        {"beef": (BEEF, by_weight(549))},
        overrides={"beef": QuantityOverride(Fraction(1), PurchaseUnit.PACKAGE)},
    )
    line = one_line(plan)
    assert line.quantity == 1
    assert Flag.OVERRIDE_STALE in line.flags


def test_a_zero_delta_changes_nothing() -> None:
    tacos = meal("meal-1", dish("Tacos", ("cheese", packages("3/4"))))
    stock: Stock = {"cheese": (CHEESE, product("16 oz"))}
    zero = {"cheese": QuantityOverride(Fraction(0), PurchaseUnit.PACKAGE)}
    assert build_list(plan_input([tacos], stock, overrides=zero), NOW) == build_list(
        plan_input([tacos], stock), NOW
    )


def test_have_it_is_never_short() -> None:
    plan = plan_input(
        [meal("meal-1", dish("Tacos", ("cheese", packages("3/4"))))],
        {"cheese": (CHEESE, product("16 oz"))},
        have_it={"cheese"},
        overrides={"cheese": QuantityOverride(Fraction(-1), PurchaseUnit.PACKAGE)},
    )
    line = one_line(plan)
    assert line.leftover is None
    assert Flag.SHORT not in line.flags


def test_build_list_needs_a_timezone_aware_now() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_list(cheese(), datetime(2026, 10, 6, 14, 0))  # noqa: DTZ001 - on purpose


# ---- the plan input ------------------------------------------------------------------------------


def test_a_plan_is_immutable() -> None:
    items = {"cheese": CHEESE}
    products = {"cheese": product("16 oz")}
    plan = PlanInput(meals=(), items=items, products=products)
    items["eggs"] = Item("eggs", "Sample Farm Eggs")  # changing what was passed in...
    products.clear()
    assert list(plan.items) == ["cheese"]  # ...doesn't change the plan
    assert plan.products["cheese"] == product("16 oz")
    with pytest.raises(TypeError):
        cast(Any, plan.items)["eggs"] = CHEESE
    same = PlanInput(meals=(), items={"cheese": CHEESE}, products={"cheese": product("16 oz")})
    assert plan == same
    assert hash(plan) == hash(same)


def test_with_meal_adds_one_meal() -> None:
    plan = cheese(meal("meal-1", dish("Tacos", ("cheese", packages("1/2")))))
    bigger = plan.with_meal(meal("meal-2", dish("Nachos", ("cheese", packages("1/2")))))
    assert [m.id for m in bigger.meals] == ["meal-1", "meal-2"]
    assert len(plan.meals) == 1
    assert one_line(bigger).need == 1


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda: cheese(meal("meal-1", dish("Tacos", ("eggs", packages("1"))))), "unknown item"),
        (
            lambda: cheese(
                meal("meal-1", dish("Tacos", ("cheese", packages("1")))),
                meal("meal-1", dish("Nachos", ("cheese", packages("1")))),
            ),
            "two meals share an id",
        ),
        (
            lambda: plan_input([], {}, extras=[Extra("extra-1", "eggs", None, Fraction(1))]),
            "unknown item",
        ),
        (
            lambda: plan_input([], {"eggs": (CHEESE, None)}),
            "holds item",
        ),
    ],
)
def test_a_plan_must_make_sense(build: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build()


def test_extras_and_meals_must_make_sense() -> None:
    with pytest.raises(ValueError, match="more than zero"):
        Extra("extra-1", None, "candles", Fraction(0))
    with pytest.raises(ValueError, match="an item or some text"):
        Extra("extra-1", None, "", Fraction(1))
    with pytest.raises(ValueError, match="more than zero"):
        meal("meal-1", dish("Tacos"), scale="0")


# ---- words for the screens -----------------------------------------------------------------------


def a_line(unit: PurchaseUnit, quantity: str, *, at_least: bool = False) -> Line:
    base = one_line(cheese(meal("meal-1", dish("Tacos", ("cheese", packages("1"))))))
    return replace(base, unit=unit, quantity=Fraction(quantity), at_least=at_least)


@pytest.mark.parametrize(
    ("unit", "quantity", "size", "at_least", "text"),
    [
        (PurchaseUnit.PACKAGE, "2", "16 oz box", False, "2 boxes"),
        (PurchaseUnit.PACKAGE, "1", "16 oz", False, "1 package"),
        (PurchaseUnit.PACKAGE, "3", "16 oz", False, "3 packages"),
        (PurchaseUnit.PACKAGE, "1", "3 lb bag", False, "1 bag"),
        (PurchaseUnit.PACKAGE, "3", "each", False, "3"),
        (PurchaseUnit.PACKAGE, "2", "6 ct", False, "2 packages"),
        (PurchaseUnit.PACKAGE, "2", "12 ct box", False, "2 boxes"),
        (PurchaseUnit.PACKAGE, "2", "12 x 12 fl oz can", False, "2 packages"),
        (PurchaseUnit.PACKAGE, "1", "Varies", True, "at least 1 package"),
        (PurchaseUnit.PACKAGE, "1", None, False, "1 package"),
        (PurchaseUnit.PACKAGE, "0", "16 oz", False, "0 packages"),
        (PurchaseUnit.PACKAGE, "1/2", "16 oz", False, "1/2 package"),
        (PurchaseUnit.EACH, "3", "per lb", False, "3"),
        (PurchaseUnit.EACH, "3", None, True, "at least 3"),
        (PurchaseUnit.POUND, "7/4", "per lb", False, "1 3/4 lb"),
        (PurchaseUnit.POUND, "1/4", "per lb", True, "at least 1/4 lb"),
    ],
)
def test_quantity_text(
    unit: PurchaseUnit, quantity: str, size: str | None, at_least: bool, text: str
) -> None:
    line = a_line(unit, quantity, at_least=at_least)
    assert quantity_text(line, None if size is None else parse_size(size)) == text


@pytest.mark.parametrize(
    ("unit", "quantity", "size", "words"),
    [
        (PurchaseUnit.PACKAGE, "2", None, "2 packages"),  # an extra of an unlinked item
        (PurchaseUnit.PACKAGE, "1", "1/2 gal", "1 package"),
        (PurchaseUnit.PACKAGE, "2", "3 lb bag", "2 bags"),
        (PurchaseUnit.PACKAGE, "2", "each", "2"),
        (PurchaseUnit.POUND, "1", "per lb", "1 lb"),
        (PurchaseUnit.POUND, "5/4", None, "1 1/4 lb"),
        (PurchaseUnit.EACH, "2", None, "2"),
    ],
)
def test_quantity_words_for_an_extra(
    unit: PurchaseUnit, quantity: str, size: str | None, words: str
) -> None:
    assert (
        quantity_words(unit, Fraction(quantity), None if size is None else parse_size(size))
        == words
    )


def test_quantity_words_refuse_floats() -> None:
    with pytest.raises(TypeError):
        quantity_words(PurchaseUnit.POUND, cast(Any, 1.5), None)


@pytest.mark.parametrize(
    ("size", "regular", "promo", "cents", "unit", "text"),
    [
        ("16 oz", 400, None, Fraction(25), Unit.OZ, "$0.25 per oz"),
        ("16 oz", 400, 320, Fraction(20), Unit.OZ, "$0.20 per oz"),  # today's sale price
        ("1 lb", 499, None, Fraction(499, 16), Unit.OZ, "$0.31 per oz"),
        ("64 fl oz", 349, None, Fraction(349, 64), Unit.FL_OZ, "$0.055 per fl oz"),
        ("12 x 12 fl oz", 599, None, Fraction(599, 144), Unit.FL_OZ, "$0.042 per fl oz"),
        ("6 ct", 250, None, Fraction(125, 3), Unit.EACH, "$0.42 each"),
        ("8 oz bag", 1250, None, Fraction(625, 4), Unit.OZ, "$1.56 per oz"),
    ],
)
def test_unit_price(
    size: str, regular: int, promo: int | None, cents: Fraction, unit: Unit, text: str
) -> None:
    assert unit_price(product(size, regular=regular, promo=promo), NOW) == UnitPrice(
        cents, unit, text
    )


def test_unit_price_of_metric_sizes_is_per_ounce() -> None:
    liter = unit_price(product("1 L", regular=199), NOW)
    assert liter is not None
    assert (liter.unit, liter.text) == (Unit.FL_OZ, "$0.059 per fl oz")
    grams = unit_price(product("500 g", regular=300), NOW)
    assert grams is not None
    assert (grams.unit, grams.text) == (Unit.OZ, "$0.17 per oz")


def test_unit_price_by_the_pound() -> None:
    assert unit_price(by_weight(149), NOW) == UnitPrice(Fraction(149), Unit.LB, "$1.49 per lb")
    assert unit_price(by_weight(1299, promo=999), NOW) == UnitPrice(
        Fraction(999), Unit.LB, "$9.99 per lb"
    )


@pytest.mark.parametrize(
    "p",
    [
        product("Varies"),
        product("16 oz", regular=None),
        product("16 oz", regular=0),
        product("16 oz", priced=False),
        by_weight(None),
    ],
)
def test_unit_price_needs_a_price_and_a_size(p: Product) -> None:
    assert unit_price(p, NOW) is None


def test_a_size_used_is_the_households_for_its_own_product() -> None:
    juice = Item(
        "juice", "Sample Orange Juice", PackageSize(None, Quantity(Fraction(64), Unit.FL_OZ))
    )
    plan = plan_input(
        [meal("meal-1", dish("Brunch", ("juice", measure("2", Unit.CUP))))],
        {"juice": (juice, product("64 oz"))},
    )
    line = one_line(plan)
    assert line.size == juice.size_override
    assert line.need == Fraction(1, 4)


# ---- pricing a saved quantity again (Shop this again) -------------------------------------------


def test_a_saved_quantity_is_priced_like_a_list_line() -> None:
    sale = product("1 lb", regular=549, promo=499)
    price = price_quantity(PurchaseUnit.PACKAGE, Fraction(3), sale, None, NOW)
    assert price is not None
    assert (price.unit_cents, price.cost_cents, price.regular_cents) == (499, 1497, 1647)
    assert (price.savings_cents, price.on_sale) == (150, True)
    # Pounds round half-up once (W2): 1 1/2 lb at $2.99 is 448.5 -> 449.
    loose = price_quantity(PurchaseUnit.POUND, Fraction(3, 2), by_weight(299), None, NOW)
    assert loose is not None and loose.cost_cents == 449


def test_pieces_need_a_weight_and_nothing_prices_without_a_regular_price() -> None:
    onions = by_weight(149)
    unweighed = price_quantity(PurchaseUnit.EACH, Fraction(3), onions, None, NOW)
    assert unweighed is not None and unweighed.cost_cents is None
    weighed = price_quantity(PurchaseUnit.EACH, Fraction(3), onions, Fraction(1, 2), NOW)
    assert weighed is not None and weighed.cost_cents == 224  # W3
    assert price_quantity(PurchaseUnit.PACKAGE, Fraction(1), None, None, NOW) is None
    promo_only = product("16 oz", regular=None, promo=299)
    assert price_quantity(PurchaseUnit.PACKAGE, Fraction(1), promo_only, None, NOW) is None
