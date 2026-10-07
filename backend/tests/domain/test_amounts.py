"""amounts.py: amount -> share (PLAN §8.4), the picker (§8.7) and its live preview (UX §4.10).

Case IDs (A1, W4, L9…) are the rows of the PLAN §8.5 table. "-> N packages" is the share rounded
up, which is what the list (M2) will buy.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from dinnerbell.domain.amounts import (
    EACH_WEIGHT_MAX,
    EACH_WEIGHT_MIN,
    Contribution,
    EachWeightQuestion,
    absolutize,
    amount_options,
    contribution,
    resolve_each_weight,
    share_cost,
    share_text,
    validate_amount,
)
from dinnerbell.domain.models import Amount, AmountKind, Flag, InvalidAmount, Item, Product, SoldBy
from dinnerbell.domain.money import dollars_to_exact_cents
from dinnerbell.domain.rational import q, round_half_up
from dinnerbell.domain.sizes import PackageSize, parse_size
from dinnerbell.domain.units import Quantity, Unit, ratio
from tests.domain.builders import (
    NOW,
    SIZE_CORPUS,
    by_weight,
    count,
    item,
    measure,
    offered_amounts,
    packages,
    product,
)


def share(a: Amount, it: Item, p: Product | None) -> Fraction:
    """The converted share of a package, asserting nothing else was set."""
    c = contribution(a, it, p, p)
    assert c == Contribution(packages=c.packages), c
    return c.packages


def rejection(a: Amount, it: Item, p: Product | None) -> str:
    with pytest.raises(InvalidAmount) as caught:
        validate_amount(a, it, p)
    return caught.value.message


# ---- A: amount -> share ------------------------------------------------------------------------


def test_a1_part_of_a_package() -> None:
    assert share(packages("3/4"), item(), product("16 oz")) == Fraction(3, 4)


def test_a2_a_weight_of_a_weight_package() -> None:
    assert share(measure("6", Unit.OZ), item(), product("16 oz")) == Fraction(3, 8)


def test_a3_more_than_one_package_rounds_up_once() -> None:
    needed = share(measure("1.5", Unit.LB), item(), product("1 lb"))
    assert needed == Fraction(3, 2)
    assert math.ceil(needed) == 2
    assert (math.ceil(needed) - needed) * 1 == Fraction(1, 2)  # 1/2 lb left of the 1 lb packages


def test_a4_sold_by_weight_is_pounds_never_packages() -> None:
    beef = by_weight(549)
    assert contribution(measure("1.5", Unit.LB), item(), beef, beef) == Contribution(
        lb=Fraction(3, 2)
    )
    assert share_cost(measure("1.5", Unit.LB), item(), beef, NOW) == 824  # 823.5 rounds up


def test_a5_cups_of_a_fluid_package() -> None:
    assert share(measure("2", Unit.CUP), item(), product("64 fl oz")) == Fraction(1, 4)


def test_a6_a_spoonful_still_buys_a_package() -> None:
    needed = share(measure("1", Unit.TBSP), item(), product("1 gal"))
    assert needed == Fraction(1, 256)
    assert math.ceil(needed) == 1


def test_a7_a_count_of_a_counted_package() -> None:
    assert share(count("3"), item(), product("6 ct")) == Fraction(1, 2)


def test_a8_cans_or_fluid_ounces_of_a_multipack() -> None:
    twelve_pack = product("12 x 12 fl oz")
    assert share(count("2"), item(), twelve_pack) == Fraction(1, 6)
    assert share(measure("24", Unit.FL_OZ), item(), twelve_pack) == Fraction(1, 6)


def test_a9_the_rounded_metric_text_is_ignored() -> None:
    assert share(measure("2", Unit.CUP), item(), product("16 fl oz (473 mL)")) == 1
    as_473_ml = ratio(Quantity(q("2"), Unit.CUP), Quantity(q("473"), Unit.ML))
    assert math.ceil(as_473_ml) == 2  # why the parser drops "(473 mL)"


def test_a10_grams_of_a_pound_package() -> None:
    needed = share(measure("250", Unit.G), item(), product("1 lb"))
    assert needed == Fraction(25000000, 45359237)
    assert math.ceil(needed) == 1


def test_a11_cups_of_a_weight_package_are_rejected_at_entry() -> None:
    cheese, cup = product("16 oz"), measure("1", Unit.CUP)
    assert rejection(cup, item(), cheese) == (
        "The package size (16 oz) is a weight, so cups don't work here. "
        "Choose part of the package or a weight."
    )
    assert contribution(cup, item(), cheese, cheese) == Contribution(
        unconverted=cup, flags=frozenset({Flag.NOT_CONVERTIBLE})
    )


def test_a12_a_count_from_a_weight_bag_uses_the_each_weight() -> None:
    needed = share(count("3"), item(each_weight="1/2"), product("3 lb bag"))
    assert needed == Fraction(1, 2)
    assert math.ceil(needed) == 1


def test_a13_a_count_from_a_weight_bag_needs_an_each_weight() -> None:
    onions, three = product("3 lb bag"), count("3")
    assert contribution(three, item(), onions, onions) == Contribution(
        unconverted=three, flags=frozenset({Flag.NEEDS_EACH_WEIGHT})
    )
    assert rejection(three, item(), onions) == (
        "To use a count here, first set about how much one weighs."
    )


def test_a14_a_weight_on_an_unreadable_size() -> None:
    unknown, six_oz = product("Varies"), measure("6", Unit.OZ)
    assert rejection(six_oz, item(), unknown) == (
        "This item's package size couldn't be read. "
        "Choose part of the package, or fix the size first."
    )
    built = contribution(six_oz, item(), unknown, unknown)  # an older line, at build time
    assert built.unconverted == six_oz  # kept as entered, so the list can say "6 oz needed"
    assert built.flags == {Flag.SIZE_UNKNOWN}


def test_a15_part_of_a_package_works_without_a_size() -> None:
    unknown = product("Varies")
    needed = share(packages("1/2"), item(), unknown)
    assert needed == Fraction(1, 2)
    assert math.ceil(needed) == 1
    assert share_cost(packages("1/2"), item(), unknown, NOW) == 125  # priced


# ---- W: each-weight ----------------------------------------------------------------------------


def test_w4_a_sane_kroger_estimate_gives_the_each_weight() -> None:
    on_sale = by_weight(149, promo=129, each_estimate=Fraction(75))
    assert resolve_each_weight(item(), on_sale) == (Fraction(75, 149), True)  # True: "est."
    assert share_cost(count("3"), item(), on_sale, NOW) == 195
    regular = by_weight(149, each_estimate=Fraction(75))
    assert share_cost(count("3"), item(), regular, NOW) == 225  # 30 saved


def test_w5_an_estimate_under_one_ounce_is_not_trusted() -> None:
    estimate = dollars_to_exact_cents("0.0995")
    assert estimate == Fraction(199, 20)
    onions = by_weight(219, each_estimate=estimate)
    assert Fraction(199, 20) / 219 == Fraction(199, 4380) < EACH_WEIGHT_MIN
    assert resolve_each_weight(item(), onions) == (None, False)
    assert share_cost(count("3"), item(), onions, NOW) is None  # "3 onions", no price
    assert share_text(count("3"), item(), onions) == "About 3"


def test_w6_an_estimate_equal_to_the_pound_price_is_not_trusted() -> None:
    assert resolve_each_weight(item(), by_weight(149, each_estimate=Fraction(149))) == (
        None,
        False,
    )


@pytest.mark.parametrize(
    ("estimate", "expected"),
    [
        (Fraction(10), (Fraction(1, 16), True)),  # 1 oz exactly
        (Fraction(9), (None, False)),
        (Fraction(800), (Fraction(5), True)),  # 5 lb exactly
        (Fraction(801), (None, False)),
        (None, (None, False)),
    ],
)
def test_the_estimate_is_trusted_from_one_ounce_to_five_pounds(
    estimate: Fraction | None, expected: tuple[Fraction | None, bool]
) -> None:
    assert resolve_each_weight(item(), by_weight(160, each_estimate=estimate)) == expected
    assert (EACH_WEIGHT_MIN, EACH_WEIGHT_MAX) == (Fraction(1, 16), Fraction(5))


def test_the_households_each_weight_wins_and_estimates_need_a_pound_price() -> None:
    estimated = by_weight(149, each_estimate=Fraction(75))
    assert resolve_each_weight(item(each_weight="3/4"), estimated) == (Fraction(3, 4), False)
    assert resolve_each_weight(item(), by_weight(None, each_estimate=Fraction(75))) == (
        None,
        False,
    )
    unit_sold = product("3 lb bag", each_estimate=Fraction(75))
    assert resolve_each_weight(item(), unit_sold) == (None, False)
    assert resolve_each_weight(item(), None) == (None, False)


def test_w8_cups_of_something_sold_by_weight_are_rejected() -> None:
    loose, cup = by_weight(), measure("1", Unit.CUP)
    assert rejection(cup, item(), loose) == (
        "This is sold by the pound, so cups don't work here. Choose a weight or a count."
    )
    assert contribution(cup, item(), loose, loose).flags == {Flag.NOT_CONVERTIBLE}


def test_a_count_of_something_sold_by_weight_is_pieces_until_list_time() -> None:
    loose = by_weight()
    assert contribution(count("3"), item(), loose, loose) == Contribution(each=Fraction(3))
    validate_amount(count("3"), item(), loose)  # accepted: the picker asks for the weight


# ---- swaps (the contribution side of L9-L13) ---------------------------------------------------


EIGHT_OZ = product("8 oz", regular=250, product_id="0000000000001")
TWO_LB = product("2 lb", regular=899, product_id="0000000000002")


def test_l9_a_weight_carries_over_to_the_swapped_product() -> None:
    swapped = contribution(measure("6", Unit.OZ), item(), TWO_LB, EIGHT_OZ, swapped=True)
    assert swapped == Contribution(packages=Fraction(3, 16))
    assert (1 - swapped.packages) * 2 == Fraction(13, 8)  # 13/8 lb left of the 2 lb package


def test_l10_part_of_a_package_keeps_its_absolute_size() -> None:
    bigger = product("32 oz", product_id="0000000000002")
    swapped = contribution(packages("1/2"), item(), bigger, product("16 oz"), swapped=True)
    assert swapped == Contribution(packages=Fraction(1, 4))


def test_l11_an_unreadable_original_size_buys_the_same_share() -> None:
    original = product("Varies", product_id="0000000000001")
    other = product("16 oz", product_id="0000000000002")
    swapped = contribution(packages("1/2"), item(), other, original, swapped=True)
    assert swapped == Contribution(packages=Fraction(1, 2), flags=frozenset({Flag.APPROX_SWAP}))


def test_l12_sizes_that_cannot_compare_keep_the_share() -> None:
    six_count = product("6 ct", product_id="0000000000002")
    swapped = contribution(measure("6", Unit.OZ), item(), six_count, product("16 oz"), swapped=True)
    assert swapped == Contribution(packages=Fraction(3, 8), flags=frozenset({Flag.APPROX_SWAP}))


def test_l13_a_bag_swapped_to_loose_by_the_pound() -> None:
    loose = by_weight(149, product_id="0000000000002")
    swapped = contribution(packages("1/2"), item(), loose, product("3 lb bag"), swapped=True)
    assert swapped == Contribution(lb=Fraction(3, 2))
    assert round_half_up(swapped.lb * 149) == 224


def test_a_swap_that_can_never_convert_stays_visible() -> None:
    six_count = product("6 ct", product_id="0000000000002")
    cup = measure("1", Unit.CUP)
    swapped = contribution(cup, item(), six_count, product("Varies"), swapped=True)
    assert swapped == Contribution(unconverted=cup, flags=frozenset({Flag.NOT_CONVERTIBLE}))


def test_swapping_to_the_same_product_changes_nothing() -> None:
    for size in ("12 x 12 fl oz", "per lb", "6 ct", "Varies"):
        same = product(size)
        for a in (packages("1/2"), count("2"), measure("1", Unit.CUP), measure("4", Unit.OZ)):
            assert contribution(a, item(), same, same, swapped=True) == contribution(
                a, item(), same, same
            )


def test_the_households_size_applies_only_to_its_own_product() -> None:
    juice = item(size=PackageSize(None, Quantity(q("64"), Unit.FL_OZ)))  # fixed from "64 oz"
    own = product("64 oz")
    assert contribution(measure("2", Unit.CUP), juice, own, own) == Contribution(
        packages=Fraction(1, 4)
    )
    other = product("32 oz", product_id="0000000000002")  # read as a weight; can't compare
    assert contribution(measure("2", Unit.CUP), juice, other, own, swapped=True) == Contribution(
        packages=Fraction(1, 4), flags=frozenset({Flag.APPROX_SWAP})
    )


def test_absolutize_gives_the_count_form_first() -> None:
    assert absolutize(packages("1/2"), parse_size_or_fail("12 x 12 fl oz")) == (
        count("6"),
        measure("72", Unit.FL_OZ),
    )
    assert absolutize(packages("1/2"), parse_size_or_fail("3 lb bag")) == (measure("3/2", Unit.LB),)


def parse_size_or_fail(text: str) -> PackageSize:
    size = parse_size(text)
    assert isinstance(size, PackageSize)
    return size


# ---- what the picker offers (PLAN §8.7) ----------------------------------------------------------


def kinds(p: Product | None, it: Item | None = None) -> list[AmountKind]:
    return [option.kind for option in amount_options(it or item(), p).kinds]


def test_a_weight_package_offers_parts_and_weights() -> None:
    options = amount_options(item(), product("16 oz"))
    assert [o.kind for o in options.kinds] == [AmountKind.PACKAGES, AmountKind.MEASURE]
    parts = options.option(AmountKind.PACKAGES)
    assert parts is not None
    assert [a.value for a in parts.presets] == [q("1/4"), q("1/2"), q("3/4"), q("1"), q("2")]
    assert parts.step == Fraction(1, 4)
    weights = options.option(AmountKind.MEASURE)
    assert weights is not None
    assert weights.units == (Unit.OZ, Unit.LB, Unit.G, Unit.KG)
    assert (options.each_weight, options.fix_size) == (None, False)


def test_a_weight_package_offers_counts_once_an_each_weight_is_set() -> None:
    assert kinds(product("3 lb bag"), item(each_weight="1/2")) == [
        AmountKind.PACKAGES,
        AmountKind.MEASURE,
        AmountKind.COUNT,
    ]


def test_a_fluid_package_offers_kitchen_measures() -> None:
    options = amount_options(item(), product("64 fl oz"))
    assert [o.kind for o in options.kinds] == [AmountKind.PACKAGES, AmountKind.MEASURE]
    spoons = options.option(AmountKind.MEASURE)
    assert spoons is not None
    assert spoons.units == (Unit.TSP, Unit.TBSP, Unit.CUP, Unit.FL_OZ)
    assert spoons.presets == (
        measure("1", Unit.TSP),
        measure("1", Unit.TBSP),
        measure("1/4", Unit.CUP),
        measure("1/2", Unit.CUP),
        measure("1", Unit.CUP),
    )


@pytest.mark.parametrize("size", ["6 ct", "each", "1 dozen"])
def test_a_counted_package_offers_counts_and_packages(size: str) -> None:
    options = amount_options(item(), product(size))
    assert [o.kind for o in options.kinds] == [AmountKind.COUNT, AmountKind.PACKAGES]
    counts = options.option(AmountKind.COUNT)
    assert counts is not None
    assert counts.step == Fraction(1, 2)


def test_a_multipack_offers_counts_its_measure_and_packages() -> None:
    assert kinds(product("12 x 12 fl oz")) == [
        AmountKind.COUNT,
        AmountKind.MEASURE,
        AmountKind.PACKAGES,
    ]


def test_sold_by_weight_offers_weights_and_counts_and_asks_what_one_weighs() -> None:
    options = amount_options(item(), by_weight(149, each_estimate=Fraction(75)))
    assert [o.kind for o in options.kinds] == [AmountKind.MEASURE, AmountKind.COUNT]
    pounds = options.option(AmountKind.MEASURE)
    assert pounds is not None
    assert pounds.units[0] is Unit.LB
    assert pounds.presets == (measure("1/2", Unit.LB), measure("1", Unit.LB))
    assert options.each_weight == EachWeightQuestion(
        presets=(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1)),
        prefill=Fraction(75, 149),
    )


def test_the_each_weight_question_has_no_prefill_without_a_sane_estimate() -> None:
    question = amount_options(item(), by_weight(219, each_estimate=Fraction(199, 20)))
    assert question.each_weight is not None
    assert question.each_weight.prefill is None


def test_the_each_weight_question_is_asked_once() -> None:
    assert amount_options(item(each_weight="1/2"), by_weight()).each_weight is None


def test_an_unreadable_size_offers_parts_only_and_fix_size() -> None:
    options = amount_options(item(), product("Varies"))
    assert [o.kind for o in options.kinds] == [AmountKind.PACKAGES]
    assert options.fix_size


def test_a_fixed_size_is_used_instead() -> None:
    fixed = item(size=parse_size_or_fail("12 oz"))
    options = amount_options(fixed, product("Varies"))
    assert [o.kind for o in options.kinds] == [AmountKind.PACKAGES, AmountKind.MEASURE]
    assert not options.fix_size


def test_an_item_without_a_store_product_offers_parts_and_counts() -> None:
    assert kinds(None) == [AmountKind.PACKAGES, AmountKind.COUNT]
    assert rejection(measure("6", Unit.OZ), item(), None) == (
        "This item isn't linked to a store product yet, so choose part of a package or a count."
    )


@pytest.mark.parametrize("size_text", SIZE_CORPUS)
@pytest.mark.parametrize("sold_by", list(SoldBy))
@pytest.mark.parametrize("each_weight", [None, "1/2"])
def test_the_picker_never_offers_what_cannot_convert(
    size_text: str | None, sold_by: SoldBy, each_weight: str | None
) -> None:
    it, p = item(each_weight=each_weight), product(size_text, sold_by=sold_by)
    offered = offered_amounts(amount_options(it, p))
    assert offered
    for a in offered:
        assert contribution(a, it, p, p).converted, a
        validate_amount(a, it, p)
        assert share_text(a, it, p) is not None, a
        assert share_cost(a, it, p, NOW) is not None or sold_by is SoldBy.WEIGHT, a


# ---- other messages ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "size", "message"),
    [
        (
            measure("6", Unit.OZ),
            "64 fl oz",
            "The package size (64 fl oz) is a liquid measure, not a weight. "
            "Choose part of the package, or cups, spoons or fluid ounces.",
        ),
        (
            count("2"),
            "64 fl oz",
            "The package size (64 fl oz) isn't a number of pieces, so a count doesn't work "
            "here. Choose part of the package or a measure.",
        ),
        (
            measure("1", Unit.TBSP),
            "6 ct",
            "The package size (6 ct) is a number of pieces, so tablespoons don't work here. "
            "Choose a count or part of the package.",
        ),
        (
            measure("6", Unit.OZ),
            "6 ct",
            "To use a weight here, first set about how much one weighs.",
        ),
    ],
)
def test_rejections_say_what_to_do_instead(a: Amount, size: str, message: str) -> None:
    assert rejection(a, item(), product(size)) == message


# ---- the live preview (UX §4.10) -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "it", "p", "text", "cents"),
    [
        # The UX wireframe: half of an 8 oz bag at $2.50.
        (packages("1/2"), item(), product("8 oz bag"), "About half the 8 oz bag", 125),
        # PLAN §8.7: "about 3/8 of the 16 oz bag, about $0.94" (no container: "package").
        (measure("6", Unit.OZ), item(), product("16 oz"), "About 3/8 of the 16 oz package", 94),
        (packages("1/4"), item(), product("16 oz"), "About a quarter of the 16 oz package", 63),
        (
            packages("3/4"),
            item(),
            product("16 oz"),
            "About three quarters of the 16 oz package",
            188,
        ),
        (measure("1.5", Unit.OZ), item(), product("16 oz"), "About 1/8 of the 16 oz package", 23),
        (measure("1", Unit.TBSP), item(), product("1 gal"), "A little of the 1 gal package", 1),
        (packages("1"), item(), product("8 oz bag"), "About the whole 8 oz bag", 250),
        (packages("15/16"), item(), product("8 oz bag"), "About the whole 8 oz bag", 234),
        (measure("24", Unit.OZ), item(), product("16 oz"), "About 1 1/2 packages of 16 oz", 375),
        (packages("2"), item(), product("3 lb bag"), "About 2 bags of 3 lb", 500),
        (measure("18", Unit.OZ), item(), product("16 oz"), "About 1 1/8 packages of 16 oz", 281),
        (packages("1/2"), item(), product("16.9 fl oz"), "About half the 16.9 fl oz package", 125),
        (packages("1/2"), item(), product("about 1.25 lb"), "About half the 1 1/4 lb package", 125),
        (count("3"), item(each_weight="1/2"), product("3 lb bag"), "About half the 3 lb bag", 125),
        # Packs of several pieces read in pieces: exact for whole and half pieces.
        (count("3"), item(), product("6 ct"), "3 of the 6", 125),
        (count("12"), item(), product("6 ct"), "12 (2 packages of 6)", 500),
        (count("6"), item(), product("12 ct box"), "6 of the 12", 125),
        (count("12"), item(), product("12 ct box"), "All 12", 250),
        (count("15"), item(), product("12 ct box"), "15 (about 1 1/4 boxes of 12)", 313),
        (count("3/2"), item(), product("6 ct"), "1 1/2 of the 6", 63),
        (count("1/2"), item(), product("6 ct"), "About half of one", 21),
        (count("2"), item(), product("12 x 12 fl oz"), "2 of the 12", 42),
        (measure("24", Unit.FL_OZ), item(), product("12 x 12 fl oz"), "2 of the 12", 42),
        (
            measure("20", Unit.FL_OZ),
            item(),
            product("12 x 12 fl oz"),
            "About 1 1/2 of the 12",
            35,
        ),
        (
            count("24"),
            item(),
            product("12 x 12 fl oz can"),
            "24 (2 packages of 12)",
            500,
        ),
        # Choosing part of the package keeps the package's wording.
        (
            packages("1/2"),
            item(),
            product("12 x 12 fl oz"),
            "About half the 12 x 12 fl oz package",
            125,
        ),
        (packages("1/2"), item(), product("each"), "About half of one", 125),
        (count("1/4"), item(), product("each"), "About a quarter of one", 63),
        (count("3"), item(), product("each"), "About 3", 750),
        (count("3/2"), item(), product("each"), "About 1 1/2", 375),
        (packages("1/2"), item(), product("Varies"), "About half the package", 125),
        (packages("3"), item(), product("Varies"), "About 3 packages", 750),
        (packages("1/2"), item(), None, "About half the package", None),
        (count("2"), item(), None, "About 2", None),
    ],
)
def test_share_text_and_cost(
    a: Amount, it: Item, p: Product | None, text: str, cents: int | None
) -> None:
    assert share_text(a, it, p) == text
    assert share_cost(a, it, p, NOW) == cents


@pytest.mark.parametrize(
    ("a", "it", "text", "cents"),
    [
        (measure("1.5", Unit.LB), item(), "About 1 1/2 lb", 224),
        (measure("6", Unit.OZ), item(), "About 6 oz", 56),
        (measure("100", Unit.G), item(), "About 4 oz", 33),
        (measure("1/2", Unit.OZ), item(), "Less than 1 oz", 5),
        (measure("15.6", Unit.OZ), item(), "About 1 lb", 145),
        (measure("21", Unit.OZ), item(), "About 1 1/4 lb", 196),
        (count("3"), item(each_weight="1/2"), "About 1 1/2 lb", 224),  # W3
        (count("1"), item(each_weight="1/2"), "About 8 oz", 75),
        (packages("1/2"), item(), "About 8 oz", 75),
    ],
)
def test_share_text_and_cost_sold_by_weight(
    a: Amount, it: Item, text: str, cents: int | None
) -> None:
    loose = by_weight(149)
    assert share_text(a, it, loose) == text
    assert share_cost(a, it, loose, NOW) == cents


def test_share_text_is_none_when_the_amount_cannot_convert() -> None:
    assert share_text(measure("1", Unit.CUP), item(), product("16 oz")) is None
    assert share_text(measure("1", Unit.CUP), item(), by_weight()) is None
    assert share_text(count("3"), item(), product("3 lb bag")) is None


@pytest.mark.parametrize(
    "p",
    [
        product("16 oz", priced=False),
        product("16 oz", regular=None),
        product("16 oz", regular=0),
        product("16 oz", regular=None, promo=199),  # P7: a promo alone is not a price
    ],
)
def test_share_cost_is_none_without_a_usable_price(p: Product) -> None:
    assert share_cost(packages("1/2"), item(), p, NOW) is None


def test_share_cost_uses_the_sale_price_while_it_lasts() -> None:
    sale = product("16 oz", regular=349, promo=299)
    assert share_cost(packages("1/2"), item(), sale, NOW) == 150  # 149.5 rounds up
    ended = product("16 oz", regular=349, promo=299, promo_until=NOW)
    assert share_cost(packages("1/2"), item(), ended, NOW) == 175  # 174.5 rounds up


def test_share_cost_is_none_for_amounts_that_cannot_convert() -> None:
    assert share_cost(measure("1", Unit.CUP), item(), product("16 oz"), NOW) is None
