"""Amounts: how much a dish line needs, as a share of what the store sells (PLAN §8.4, §8.7).

The amount picker offers only what ``contribution`` can convert (``amount_options``), and
``validate_amount`` turns the rest away at entry with a plain-English message. ``share_text`` and
``share_cost`` drive the picker's live preview: "About half the 8 oz bag", about $1.25.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction

from .models import Amount, AmountKind, Flag, InvalidAmount, Item, Product, SoldBy, effective_size
from .money import effective_cents
from .rational import q, round_half_up, to_mixed
from .sizes import Container, PackageSize, Unparseable, parse_size, size_label
from .units import Dimension, Unit, convert, ratio

EACH_WEIGHT_MIN = Fraction(1, 16)  # pounds: Kroger's per-each estimate is trusted from 1 oz…
EACH_WEIGHT_MAX = Fraction(5)  # …up to 5 lb (PLAN §8.8)

_ZERO = Fraction(0)
_A_LITTLE = Fraction(1, 16)  # a share below this reads "A little of …"


@dataclass(frozen=True, slots=True)
class Contribution:
    """What one amount adds to its item's line.

    At most one of ``packages``, ``lb`` and ``each`` is set. An amount that can't be converted is
    kept as entered in ``unconverted`` (shown as "6 oz needed"), and its reason is in ``flags``.
    """

    packages: Fraction = _ZERO  # share of a package: sold by the package, or no product
    lb: Fraction = _ZERO  # pounds: sold by weight
    each: Fraction = _ZERO  # pieces: a count of something sold by weight, or with no product
    unconverted: Amount | None = None
    flags: frozenset[Flag] = frozenset()

    def __post_init__(self) -> None:
        for name, value in (("packages", self.packages), ("lb", self.lb), ("each", self.each)):
            exact = q(value)
            if exact < 0:
                raise ValueError(f"{name} can't be negative")
            object.__setattr__(self, name, exact)

    @property
    def converted(self) -> bool:
        return self.unconverted is None


@dataclass(frozen=True, slots=True)
class KindOption:
    """One way the picker lets the person say how much."""

    kind: AmountKind
    units: tuple[Unit, ...] = ()  # MEASURE: the units it can switch between; the first is default
    presets: tuple[Amount, ...] = ()  # one-tap choices
    step: Fraction | None = None  # the stepper's increment, when it has one

    def __post_init__(self) -> None:
        if self.step is not None:
            object.__setattr__(self, "step", q(self.step))


@dataclass(frozen=True, slots=True)
class EachWeightQuestion:
    """Ask "About how much does one weigh?" once: Small, Medium, Large, 1 lb or Other."""

    presets: tuple[Fraction, ...]  # pounds: Small 1/4 (4 oz), Medium 1/2, Large 3/4, then 1 lb
    prefill: Fraction | None  # pounds, from Kroger's estimate when it is sane

    def __post_init__(self) -> None:
        object.__setattr__(self, "presets", tuple(q(weight) for weight in self.presets))
        if self.prefill is not None:
            object.__setattr__(self, "prefill", q(self.prefill))


@dataclass(frozen=True, slots=True)
class AmountOptions:
    """What the amount picker offers for one item. It never offers what can't be converted."""

    kinds: tuple[KindOption, ...]  # in the order the picker shows them
    each_weight: EachWeightQuestion | None = None  # set when the picker should ask
    fix_size: bool = False  # offer "Fix size": the package size couldn't be read

    def option(self, kind: AmountKind) -> KindOption | None:
        return next((option for option in self.kinds if option.kind is kind), None)


def _measure(value: Fraction, unit: Unit) -> Amount:
    return Amount(AmountKind.MEASURE, value, unit)


_PACKAGES_OPTION = KindOption(
    AmountKind.PACKAGES,
    presets=tuple(
        Amount(AmountKind.PACKAGES, Fraction(n, d))
        for n, d in ((1, 4), (1, 2), (3, 4), (1, 1), (2, 1))
    ),
    step=Fraction(1, 4),
)
_COUNT_OPTION = KindOption(AmountKind.COUNT, step=Fraction(1, 2))
_WEIGHT_OPTION = KindOption(AmountKind.MEASURE, units=(Unit.OZ, Unit.LB, Unit.G, Unit.KG))
_KITCHEN_OPTION = KindOption(
    AmountKind.MEASURE,
    units=(Unit.TSP, Unit.TBSP, Unit.CUP, Unit.FL_OZ),
    presets=(
        _measure(Fraction(1), Unit.TSP),
        _measure(Fraction(1), Unit.TBSP),
        _measure(Fraction(1, 4), Unit.CUP),
        _measure(Fraction(1, 2), Unit.CUP),
        _measure(Fraction(1), Unit.CUP),
    ),
)
_POUND_OPTION = KindOption(
    AmountKind.MEASURE,
    units=(Unit.LB, Unit.OZ, Unit.G, Unit.KG),
    presets=(_measure(Fraction(1, 2), Unit.LB), _measure(Fraction(1), Unit.LB)),
)
_EACH_WEIGHT_PRESETS = (Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1))


def amount_options(item: Item, product: Product | None) -> AmountOptions:
    """What the picker offers for this item (PLAN §8.7)."""
    if product is None:  # no store product: parts of a package, or a count
        return AmountOptions((_PACKAGES_OPTION, _COUNT_OPTION))
    if product.sold_by is SoldBy.WEIGHT:
        question = None
        if item.each_weight is None:
            weight, estimated = resolve_each_weight(item, product)
            question = EachWeightQuestion(_EACH_WEIGHT_PRESETS, weight if estimated else None)
        return AmountOptions((_POUND_OPTION, _COUNT_OPTION), each_weight=question)
    size = effective_size(item, product)
    if isinstance(size, Unparseable):
        return AmountOptions((_PACKAGES_OPTION,), fix_size=True)
    if size.measure is None:  # "6 ct", "each"
        return AmountOptions((_COUNT_OPTION, _PACKAGES_OPTION))
    by_weight = size.measure.dimension is Dimension.MASS
    measure_option = _WEIGHT_OPTION if by_weight else _KITCHEN_OPTION
    if size.count is not None:  # a multipack: "12 x 12 fl oz"
        return AmountOptions((_COUNT_OPTION, measure_option, _PACKAGES_OPTION))
    if by_weight and item.each_weight is not None:  # "3 lb bag" of onions, one weighs 8 oz
        return AmountOptions((_PACKAGES_OPTION, measure_option, _COUNT_OPTION))
    return AmountOptions((_PACKAGES_OPTION, measure_option))


def validate_amount(a: Amount, item: Item, product: Product | None) -> None:
    """Raise InvalidAmount, with a message for the person, if ``a`` can't be converted."""
    size = effective_size(item, product)
    result = _direct(a, item, product, size)
    if isinstance(result, Flag):
        raise InvalidAmount(_rejection(a, product, size, result))


def share_text(a: Amount, item: Item, product: Product | None) -> str | None:
    """The preview's first line: "About half the 8 oz bag". None if ``a`` can't be converted."""
    size = effective_size(item, product)
    result = _direct(a, item, product, size)
    if isinstance(result, Flag):
        return None
    if product is not None and product.sold_by is SoldBy.WEIGHT:
        pounds = result.lb
        if result.each:
            each_lb, _ = resolve_each_weight(item, product)
            if each_lb is None:
                return _pieces_text(result.each)
            pounds += result.each * each_lb
        return _weight_text(pounds)
    if result.each:  # a count of an item with no store product
        return _pieces_text(result.each)
    return _package_text(result.packages, size)


def share_cost(a: Amount, item: Item, product: Product | None, now: datetime) -> int | None:
    """This amount's share of the cost in cents, at today's price. None when there's no price."""
    if product is None or product.price is None or not product.price.regular:
        return None
    result = _direct(a, item, product, effective_size(item, product))
    if isinstance(result, Flag):
        return None
    cents = effective_cents(product.price, now)
    if product.sold_by is SoldBy.UNIT:
        return round_half_up(result.packages * cents)
    pounds = result.lb
    if result.each:
        each_lb, _ = resolve_each_weight(item, product)
        if each_lb is None:
            return None
        pounds += result.each * each_lb
    return round_half_up(pounds * cents)


def resolve_each_weight(item: Item, product: Product | None) -> tuple[Fraction | None, bool]:
    """Pounds per piece, and whether it came from Kroger's estimate (the "est." badge).

    The household's value wins. Otherwise, for items sold by weight, Kroger's per-each estimate
    divided by the price per pound, if it is between 1 oz and 5 lb and differs from that price.
    """
    if item.each_weight is not None:
        return item.each_weight, False
    if product is None or product.sold_by is not SoldBy.WEIGHT or product.price is None:
        return None, False
    estimate, regular = product.price.each_estimate, product.price.regular
    if estimate is None or not regular or estimate == regular:
        return None, False
    weight = estimate / regular
    if EACH_WEIGHT_MIN <= weight <= EACH_WEIGHT_MAX:
        return weight, True
    return None, False


def contribution(
    a: Amount,
    item: Item,
    product: Product | None,
    original: Product | None = None,
    swapped: bool = False,
) -> Contribution:
    """Turn an amount into packages, pounds or pieces of ``product`` (PLAN §8.4).

    ``product`` is the product used for this trip; ``original`` is the item's own product, and
    ``swapped`` says the two differ. The household's size applies only to the item's own product.
    """
    if product is not None and swapped and not _same_product(product, original):
        return _swapped(a, item, product, original, parse_size(product.size_text))
    result = _direct(a, item, product, effective_size(item, product))
    return result if isinstance(result, Contribution) else _unconverted(a, result)


def absolutize(a: Amount, size: PackageSize) -> tuple[Amount, ...]:
    """A part-of-a-package amount as absolute amounts: the count form first, then the measure."""
    forms: list[Amount] = []
    if size.count is not None:
        forms.append(Amount(AmountKind.COUNT, a.value * size.count))
    if size.measure is not None:
        forms.append(_measure(a.value * size.measure.value, size.measure.unit))
    return tuple(forms)


# ---- conversion --------------------------------------------------------------------------------


def _direct(
    a: Amount, item: Item, product: Product | None, size: PackageSize | Unparseable
) -> Contribution | Flag:
    """``direct()`` from PLAN §8.4: the amount in terms of ``product``, or why it can't be."""
    if product is None:
        if a.kind is AmountKind.PACKAGES:
            return Contribution(packages=a.value)
        if a.kind is AmountKind.COUNT:
            return Contribution(each=a.value)
        return Flag.NOT_CONVERTIBLE
    amount = a.quantity
    if product.sold_by is SoldBy.WEIGHT:  # Kroger prices these per pound
        if amount is not None:
            if amount.dimension is Dimension.MASS:
                return Contribution(lb=convert(amount, Unit.LB).value)
            return Flag.NOT_CONVERTIBLE  # never volume to weight
        if a.kind is AmountKind.COUNT:
            return Contribution(each=a.value)
        return Contribution(lb=a.value * (_size_lb(size) or 1))
    if a.kind is AmountKind.PACKAGES:  # works even when the size is unknown
        return Contribution(packages=a.value)
    if isinstance(size, Unparseable):
        return Flag.SIZE_UNKNOWN
    if amount is not None:
        if size.measure is not None and size.measure.dimension is amount.dimension:
            return Contribution(packages=ratio(amount, size.measure))
        if size.count is not None and amount.dimension is Dimension.MASS:
            if item.each_weight is None:
                return Flag.NEEDS_EACH_WEIGHT
            pounds = convert(amount, Unit.LB).value
            return Contribution(packages=pounds / item.each_weight / size.count)
        return Flag.NOT_CONVERTIBLE
    if size.count is not None:
        return Contribution(packages=a.value / size.count)
    size_lb = _size_lb(size)
    if size_lb is None:
        return Flag.NOT_CONVERTIBLE
    if item.each_weight is None:
        return Flag.NEEDS_EACH_WEIGHT
    return Contribution(packages=a.value * item.each_weight / size_lb)


def _swapped(
    a: Amount,
    item: Item,
    product: Product,
    original: Product | None,
    size: PackageSize | Unparseable,
) -> Contribution:
    """A swap to a different product: keep the absolute amount if the sizes compare."""
    if a.kind is AmountKind.PACKAGES and original is not None:
        original_size = effective_size(item, original)
        if isinstance(original_size, PackageSize):
            for absolute in absolutize(a, original_size):
                result = _direct(absolute, item, product, size)
                if isinstance(result, Contribution):
                    return result
    result = _direct(a, item, product, size)
    if isinstance(result, Contribution) and a.kind is not AmountKind.PACKAGES:
        return result
    # The sizes can't be compared: buy the same share of the new product and flag "check amount".
    share = a.value if a.kind is AmountKind.PACKAGES else _share_of(a, item, original)
    if share is not None:
        approximate = frozenset({Flag.APPROX_SWAP})
        if product.sold_by is SoldBy.WEIGHT:
            return Contribution(lb=share * (_size_lb(size) or 1), flags=approximate)
        return Contribution(packages=share, flags=approximate)
    return _unconverted(a, result if isinstance(result, Flag) else Flag.NOT_CONVERTIBLE)


def _share_of(a: Amount, item: Item, original: Product | None) -> Fraction | None:
    """The share of the original product's package that ``a`` is, if that can be known."""
    if original is None:
        return None
    original_size = effective_size(item, original)
    result = _direct(a, item, original, original_size)
    if isinstance(result, Flag) or result.each:
        return None
    if original.sold_by is SoldBy.WEIGHT:
        return result.lb / (_size_lb(original_size) or 1)
    return result.packages


def _same_product(product: Product, original: Product | None) -> bool:
    return original is not None and original.product_id == product.product_id


def _size_lb(size: PackageSize | Unparseable) -> Fraction | None:
    if isinstance(size, PackageSize) and size.measure is not None:
        if size.measure.dimension is Dimension.MASS:
            return convert(size.measure, Unit.LB).value
    return None


def _unconverted(a: Amount, reason: Flag) -> Contribution:
    return Contribution(unconverted=a, flags=frozenset({reason}))


# ---- words ---------------------------------------------------------------------------------------

_PART_WORDS = {
    Fraction(1, 4): "a quarter of",
    Fraction(1, 2): "half",
    Fraction(3, 4): "three quarters of",
}
_UNIT_WORDS: dict[Unit, str] = {
    Unit.G: "grams",
    Unit.KG: "kilograms",
    Unit.OZ: "ounces",
    Unit.LB: "pounds",
    Unit.ML: "milliliters",
    Unit.L: "liters",
    Unit.FL_OZ: "fluid ounces",
    Unit.TSP: "teaspoons",
    Unit.TBSP: "tablespoons",
    Unit.CUP: "cups",
    Unit.PT: "pints",
    Unit.QT: "quarts",
    Unit.GAL: "gallons",
    Unit.EACH: "pieces",
}


def _part(share: Fraction) -> str:
    """Words for a share under 1, already rounded to eighths: "half", "3/8 of"."""
    return _PART_WORDS.get(share, f"{share} of")


def _package_text(share: Fraction, size: PackageSize | Unparseable) -> str:
    if isinstance(size, PackageSize) and size.measure is None and size.count == 1:
        return _pieces_text(share)  # sold one at a time ("each")
    one, many = _package_nouns(size)
    if share < _A_LITTLE:
        return f"A little of the {one}"
    eighths = round_half_up(share * 8)
    if eighths < 8:
        return f"About {_part(Fraction(eighths, 8))} the {one}"
    if eighths == 8:
        return f"About the whole {one}"
    return f"About {to_mixed(Fraction(eighths, 8))} {many}"


def _package_nouns(size: PackageSize | Unparseable) -> tuple[str, str]:
    """("8 oz bag", "bags of 8 oz"), ("package of 6", "packages of 6") or plain packages."""
    if isinstance(size, Unparseable):
        return "package", "packages"
    if size.measure is None:
        assert size.count is not None
        noun = size.container or Container.PACKAGE
        pieces = to_mixed(size.count)
        return f"{noun.value} of {pieces}", f"{noun.plural} of {pieces}"
    label = size_label(size)
    # In a multipack ("12 x 12 fl oz can") the container is each piece, not the package.
    noun = size.container if size.container and size.count is None else Container.PACKAGE
    return f"{label} {noun.value}", f"{noun.plural} of {label}"


def _pieces_text(pieces: Fraction) -> str:
    if pieces < _A_LITTLE:
        return "A little of one"
    eighths = round_half_up(pieces * 8)
    if eighths < 8:
        part = _part(Fraction(eighths, 8))
        return f"About {'half of' if part == 'half' else part} one"
    return f"About {to_mixed(Fraction(eighths, 8))}"


def _weight_text(pounds: Fraction) -> str:
    ounces = pounds * 16
    if ounces < 1:
        return "Less than 1 oz"
    whole_ounces = round_half_up(ounces)
    if whole_ounces < 16:
        return f"About {whole_ounces} oz"
    return f"About {to_mixed(Fraction(round_half_up(pounds * 4), 4))} lb"  # nearest 1/4 lb


def _rejection(
    a: Amount, product: Product | None, size: PackageSize | Unparseable, reason: Flag
) -> str:
    """Why an amount can't be used, and what to do instead, in the app's plain words."""
    if reason is Flag.SIZE_UNKNOWN:
        return (
            "This item's package size couldn't be read. "
            "Choose part of the package, or fix the size first."
        )
    if reason is Flag.NEEDS_EACH_WEIGHT:
        what = "a count" if a.kind is AmountKind.COUNT else "a weight"
        return f"To use {what} here, first set about how much one weighs."
    if product is None:
        return (
            "This item isn't linked to a store product yet, so choose part of a package or a count."
        )
    words = "counts" if a.unit is None else _UNIT_WORDS[a.unit]
    if product.sold_by is SoldBy.WEIGHT:
        return f"This is sold by the pound, so {words} don't work here. Choose a weight or a count."
    assert isinstance(size, PackageSize)
    label = size_label(size)
    if a.kind is AmountKind.COUNT:
        return (
            f"The package size ({label}) isn't a number of pieces, so a count doesn't work here. "
            "Choose part of the package or a measure."
        )
    if size.measure is None:
        return (
            f"The package size ({label}) is a number of pieces, so {words} don't work here. "
            "Choose a count or part of the package."
        )
    if size.measure.dimension is Dimension.MASS:
        return (
            f"The package size ({label}) is a weight, so {words} don't work here. "
            "Choose part of the package or a weight."
        )
    return (
        f"The package size ({label}) is a liquid measure, not a weight. "
        "Choose part of the package, or cups, spoons or fluid ounces."
    )
