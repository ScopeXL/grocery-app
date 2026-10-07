"""recommend.py: mains that use up the list's leftovers, R1 to R10 of PLAN §8.5.

Every case starts from the "Taco night" plan (total 1676): lettuce (1 ct, 199, uses 1/2),
cheese (8 oz, 250, uses 4 oz), ground beef (2 lb, 998, uses 1 lb) and shells (12 ct, 229, uses 12).
All names and prices are synthetic.
"""

from __future__ import annotations

from datetime import date, datetime
from fractions import Fraction
from typing import Any, cast

import pytest

from dinnerbell.domain.listbuild import build_list
from dinnerbell.domain.models import Dish, Item, PlanInput, Product
from dinnerbell.domain.recommend import (
    Candidate,
    Recommendation,
    _by_key,
    _shared,
    marginal_cost,
    meal_for,
    recommend,
)
from dinnerbell.domain.units import Unit
from tests.domain.builders import NOW, count, dish, meal, measure, packages, plan_input, product


def _sold(item_id: str, name: str, size: str, cents: int, n: int) -> tuple[Item, Product]:
    return Item(item_id, name), product(size, regular=cents, product_id=f"00000000000{n:02d}")


STOCK: dict[str, tuple[Item, Product | None]] = {
    "lettuce": _sold("lettuce", "Lettuce", "1 ct", 199, 1),
    "cheese": _sold("cheese", "Cheese", "8 oz", 250, 2),
    "beef": _sold("beef", "Ground beef", "2 lb", 998, 3),
    "shells": _sold("shells", "Taco shells", "12 ct", 229, 4),
    "tomatoes": _sold("tomatoes", "Tomatoes", "each", 69, 5),
    "chips": _sold("chips", "Tortilla chips", "13 oz bag", 250, 6),
    "oil": _sold("oil", "Olive oil", "16.9 fl oz", 899, 7),
    "limes": _sold("limes", "Limes", "each", 40, 8),
    "salsa": _sold("salsa", "Salsa", "16 oz", 299, 9),
    "spaghetti": _sold("spaghetti", "Spaghetti", "16 oz", 150, 10),
    "sauce": _sold("sauce", "Pasta sauce", "24 oz jar", 299, 11),
    "sour_cream": _sold("sour_cream", "Sour cream", "16 oz", 199, 12),
    "tortillas": _sold("tortillas", "Flour tortillas", "10 ct", 279, 13),
    "guacamole": _sold("guacamole", "Guacamole", "8 oz", 412, 14),
    "queso": _sold("queso", "Queso dip", "15 oz", 400, 15),
    "pico": _sold("pico", "Pico de gallo", "16 oz", 420, 16),
    "bbq": _sold("bbq", "BBQ sauce", "18 oz", 199, 17),
    "cilantro": (Item("cilantro", "Cilantro"), None),  # not linked to a store product
}
LEFTOVERS = (  # what Taco night leaves: 1/2 lettuce, 4 oz cheese, 1 lb beef
    ("lettuce", packages("1/2")),
    ("cheese", measure("4", Unit.OZ)),
    ("beef", measure("1", Unit.LB)),
)
TACO_NIGHT = dish("Taco night", *LEFTOVERS, ("shells", count("12")), dish_id="dish-taco-night")
TACO_SALAD = dish(
    "Taco salad",
    *LEFTOVERS,
    ("tomatoes", count("2")),
    ("chips", packages("1")),
    dish_id="dish-taco-salad",
)


def taco_night(*more_dishes: Dish, have_it: tuple[str, ...] = ()) -> PlanInput:
    meals = [meal("meal-1", TACO_NIGHT)]
    meals += [meal(f"meal-{n}", d) for n, d in enumerate(more_dishes, start=2)]
    return plan_input(meals, STOCK, have_it=have_it)


def main(d: Dish, *, favorite: bool = False, last_made: date | None = None) -> Candidate:
    return Candidate(d, "main", favorite=favorite, last_made=last_made)


def leftover_tacos(name: str, *lines: tuple[str, Any]) -> Dish:
    return dish(name, *LEFTOVERS, *lines, dish_id=f"dish-{name.lower().replace(' ', '-')}")


def test_the_taco_night_fixture_costs_1676() -> None:
    assert build_list(taco_night(), NOW).totals.total == 1676


def test_r1_a_main_that_uses_the_leftovers() -> None:
    plan = taco_night()
    (salad,) = recommend(plan, [main(TACO_SALAD)], NOW)
    assert salad == Recommendation(
        dish_id="dish-taco-salad",
        name="Taco salad",
        added_cents=388,  # 2 tomatoes (138) and chips (250); the rest is leftovers
        unpriced=0,
        value_cents=724,  # 99.5 + 125 + 499
        named=("Lettuce", "Cheese", "Ground beef"),
        more=0,
        text="Taco salad uses your leftover lettuce, cheese and ground beef. Adds about $4.",
    )
    with_salad = build_list(plan.with_meal(meal_for(TACO_SALAD)), NOW)
    values = _shared(TACO_SALAD, _by_key(build_list(plan, NOW)), _by_key(with_salad))
    assert values == [
        ("Lettuce", Fraction(199, 2)),
        ("Cheese", Fraction(125)),
        ("Ground beef", Fraction(499)),
    ]


def test_r2_a_main_that_shares_nothing_is_hidden() -> None:
    pasta = dish("Spaghetti", ("spaghetti", packages("1")), ("sauce", packages("1")))
    assert recommend(taco_night(), [main(pasta)], NOW) == ()


def test_r3_a_little_olive_oil_is_not_worth_a_recommendation() -> None:
    fried_rice = dish("Fried rice", ("oil", measure("2", Unit.TBSP)))
    vinaigrette = dish("Vinaigrette", ("oil", measure("2", Unit.TBSP)))
    plan = taco_night(fried_rice)
    with_it = build_list(plan.with_meal(meal_for(vinaigrette)), NOW)
    ((label, value),) = _shared(vinaigrette, _by_key(build_list(plan, NOW)), _by_key(with_it))
    assert (label, round(value)) == ("Olive oil", 53)  # 1 fl oz of 16.9 at 899
    assert recommend(plan, [main(vinaigrette)], NOW) == ()


def test_r4_a_main_made_of_leftovers_buys_nothing() -> None:
    (bowl,) = recommend(taco_night(), [main(leftover_tacos("Taco bowl"))], NOW)
    assert (bowl.added_cents, bowl.unpriced) == (0, 0)
    assert bowl.text == (
        "Taco bowl uses your leftover lettuce, cheese and ground beef. Nothing extra to buy."
    )


def test_r5_adding_under_fifty_cents_is_less_than_a_dollar() -> None:
    lime_bowl = leftover_tacos("Lime bowl", ("limes", count("1")))
    (bowl,) = recommend(taco_night(), [main(lime_bowl)], NOW)
    assert bowl.added_cents == 40
    assert bowl.text.endswith(" Adds less than $1.")


def test_r6_a_new_item_without_a_price_ranks_after_priced_meals() -> None:
    salsa_bowl = leftover_tacos("Salsa bowl", ("salsa", packages("1")), ("cilantro", count("1")))
    first, second = recommend(taco_night(), [main(salsa_bowl), main(TACO_SALAD)], NOW)
    assert (first.name, first.added_cents) == ("Taco salad", 388)  # costs more, fully priced
    assert (second.added_cents, second.unpriced) == (299, 1)
    assert second.text == (
        "Salsa bowl uses your leftover lettuce, cheese and ground beef. "
        "Adds about $3, plus 1 item without a price."
    )


def test_r7_ties_at_the_dollar_go_to_favorites_then_meals_not_made_lately() -> None:
    a = main(leftover_tacos("Guacamole tacos", ("guacamole", packages("1"))), favorite=True)
    b = main(TACO_SALAD, last_made=date(2026, 9, 15))
    c = main(leftover_tacos("Queso tacos", ("queso", packages("1"))), last_made=date(2026, 8, 1))
    d = main(leftover_tacos("Pico tacos", ("pico", packages("1"))))  # never made
    ranked = recommend(taco_night(), [b, d, c, a], NOW, limit=4)
    assert [(r.name, r.added_cents) for r in ranked] == [
        ("Guacamole tacos", 412),  # A: a favorite, about $4
        ("Pico tacos", 420),  # D: never made
        ("Queso tacos", 400),  # C: made in August
        ("Taco salad", 388),  # B: made in September
    ]


def test_r8_planned_archived_and_side_dishes_are_left_out() -> None:
    side = Candidate(leftover_tacos("Spanish rice"), "side")
    archived = Candidate(TACO_SALAD, "main", archived=True)
    already_planned = main(TACO_NIGHT)
    assert recommend(taco_night(), [side, archived, already_planned], NOW) == ()


def test_r9_names_the_three_most_valuable_and_counts_the_rest() -> None:
    nachos = dish("Nachos", ("sour_cream", measure("4", Unit.OZ)), ("salsa", measure("4", Unit.OZ)))
    loaded = leftover_tacos(
        "Loaded nachos", ("sour_cream", measure("4", Unit.OZ)), ("salsa", measure("4", Unit.OZ))
    )
    (nachos_again,) = recommend(taco_night(nachos), [main(loaded)], NOW)
    assert nachos_again.named == ("Lettuce", "Cheese", "Ground beef")  # 99.5, 125 and 499
    assert nachos_again.more == 2  # sour cream (49.75) and salsa (74.75)
    assert nachos_again.text == (
        "Loaded nachos uses your leftover lettuce, cheese, ground beef and 2 more. "
        "Nothing extra to buy."
    )


def test_r10_needing_more_than_the_leftover_buys_one_more() -> None:
    quesadillas = dish(
        "Quesadillas", ("cheese", measure("8", Unit.OZ)), ("tortillas", packages("1"))
    )
    plan = taco_night()
    (rec,) = recommend(plan, [main(quesadillas)], NOW)
    with_it = build_list(plan.with_meal(meal_for(quesadillas)), NOW)
    cheese = with_it.line("cheese")
    assert cheese is not None and cheese.quantity == 2  # one more package
    assert (rec.named, rec.value_cents, rec.added_cents) == (("Cheese",), 125, 529)
    assert rec.text == "Quesadillas uses your leftover cheese. Adds about $5."


# ---- more of the rules -------------------------------------------------------------------------


def test_marginal_cost_is_what_the_dish_adds_and_its_unpriced_lines() -> None:
    plan = taco_night()
    assert marginal_cost(plan, TACO_SALAD, NOW) == (388, 0)
    salsa_bowl = leftover_tacos("Salsa bowl", ("salsa", packages("1")), ("cilantro", count("1")))
    assert marginal_cost(plan, salsa_bowl, NOW) == (299, 1)
    assert marginal_cost(plan, TACO_NIGHT, NOW) == (229, 0)  # twice over, only the shells run out
    assert meal_for(TACO_SALAD).id == "recommend:dish-taco-salad"


def test_nothing_to_pay_but_an_unpriced_item() -> None:
    herbs = leftover_tacos("Herb tacos", ("cilantro", count("1")))
    (rec,) = recommend(taco_night(), [main(herbs)], NOW)
    assert (rec.added_cents, rec.unpriced) == (0, 1)
    assert rec.text.endswith(" Adds 1 item without a price.")


def test_have_it_items_are_never_named_or_counted() -> None:
    (salad,) = recommend(taco_night(have_it=("lettuce",)), [main(TACO_SALAD)], NOW)
    assert salad.named == ("Cheese", "Ground beef")
    assert salad.value_cents == 624


def test_names_keep_their_initials() -> None:
    ribs = dish("Ribs", ("bbq", measure("9", Unit.OZ)))
    salad = dish("BBQ chicken salad", ("lettuce", packages("1/2")), ("bbq", measure("9", Unit.OZ)))
    (rec,) = recommend(taco_night(ribs), [main(salad)], NOW)
    assert rec.text == (
        "BBQ chicken salad uses your leftover lettuce and BBQ sauce. Nothing extra to buy."
    )


def test_when_nothing_is_worth_naming_the_best_item_is_named() -> None:
    (salad,) = recommend(taco_night(), [main(TACO_SALAD)], NOW, name_min_cents=500)
    assert (salad.named, salad.more) == (("Ground beef",), 0)


def test_limits_and_thresholds() -> None:
    plan = taco_night()
    four = [main(leftover_tacos(f"Tacos {n}", ("tomatoes", count(str(n))))) for n in "1234"]
    assert len(recommend(plan, four, NOW)) == 3
    assert [r.name for r in recommend(plan, four, NOW, limit=2)] == ["Tacos 1", "Tacos 2"]
    assert recommend(plan, four, NOW, limit=0) == ()
    assert recommend(plan, [main(TACO_SALAD)], NOW, min_value_cents=1000) == ()  # uses 723.5
    assert recommend(plan, [], NOW) == ()


def test_candidates_must_make_sense() -> None:
    with pytest.raises(ValueError, match="share a dish id"):
        recommend(taco_night(), [main(TACO_SALAD), main(TACO_SALAD)], NOW)
    with pytest.raises(ValueError, match="'main' or 'side'"):
        Candidate(TACO_SALAD, "Main")
    with pytest.raises(TypeError, match="date"):
        Candidate(TACO_SALAD, "main", last_made=cast(Any, datetime(2026, 9, 1, tzinfo=NOW.tzinfo)))
    with pytest.raises(TypeError, match="True or False"):
        Candidate(TACO_SALAD, "main", favorite=cast(Any, "yes"))
    with pytest.raises(ValueError, match="unknown item"):  # its items must be in the plan
        recommend(taco_night(), [main(dish("Mystery", ("caviar", packages("1"))))], NOW)
    with pytest.raises(ValueError, match="limit can't be negative"):
        recommend(taco_night(), [], NOW, limit=-1)
    with pytest.raises(ValueError, match="timezone-aware"):
        recommend(taco_night(), [], datetime(2026, 10, 6, 14, 0))  # noqa: DTZ001 - on purpose


def test_a_recommendation_holds_only_sane_values() -> None:
    with pytest.raises(ValueError):
        Recommendation("dish-1", "Tacos", -1, 0, 100, ("Cheese",), 0, "Tacos uses …")
    with pytest.raises(TypeError):
        Recommendation("dish-1", "Tacos", cast(Any, 1.5), 0, 100, ("Cheese",), 0, "Tacos uses …")
