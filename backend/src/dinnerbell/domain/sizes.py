"""Package sizes: Kroger's size text read into an exact PackageSize (PLAN §8.3).

``parse_size`` is total: it never raises. Text it can't read comes back as ``Unparseable`` with a
reason, and the household corrects the size by hand ("Fix size"). ``format_size`` writes a size as
text that ``parse_size`` reads back to the identical value.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import cast

from .rational import q, to_mixed
from .units import Dimension, Quantity, Unit

MAX_SIZE_PART = 10**9
"""The largest numerator or denominator a size may have. Real sizes are far smaller; the limit
keeps every ``format_size`` text short enough for ``parse_size`` to read back."""


class Container(StrEnum):
    """What the package is, when the size text names it ("3 lb bag")."""

    BAG = "bag"
    BOX = "box"
    PACKAGE = "package"
    CAN = "can"
    JAR = "jar"
    BOTTLE = "bottle"
    CARTON = "carton"
    TUB = "tub"
    TRAY = "tray"
    CONTAINER = "container"
    POUCH = "pouch"
    CLAMSHELL = "clamshell"

    @property
    def plural(self) -> str:
        return f"{self.value}es" if self.value.endswith(("x", "ch")) else f"{self.value}s"


class ParseFail(StrEnum):
    """Why parse_size couldn't read a size."""

    EMPTY = "empty"  # nothing to read: None, "", "(473 mL)"
    RANGE = "range"  # "3-4 lb"
    UNKNOWN_UNIT = "unknown_unit"  # "2 cu ft", "Varies"
    NON_POSITIVE = "non_positive"  # "0 oz"
    MULTIPLE = "multiple"  # two sizes: "12 oz, 2 ct"
    TRAILING = "trailing"  # a size followed by other words: "16 oz bag of chips"
    TOO_LARGE = "too_large"  # a number far too long to be a real size


@dataclass(frozen=True, slots=True)
class PackageSize:
    """A package's size: pieces, a total weight or volume, or both (a multipack)."""

    count: Fraction | None  # pieces per package: "6 ct" -> 6, "12 x 12 fl oz" -> 12, "each" -> 1
    measure: Quantity | None  # total weight or volume: "12 x 12 fl oz" -> 144 fl oz
    approximate: bool = False  # "about 1.25 lb"
    container: Container | None = None  # "3 lb bag" -> bag

    def __post_init__(self) -> None:
        flag = cast(object, self.approximate)
        if not isinstance(flag, bool):
            raise TypeError("approximate must be True or False")
        if self.count is None and self.measure is None:
            raise ValueError("a package size needs a count, a measure or both")
        if self.count is not None:
            object.__setattr__(self, "count", _size_part(q(self.count)))
        if self.measure is not None:
            if self.measure.dimension is Dimension.COUNT:
                raise ValueError("a count belongs in count, not in measure")
            _size_part(self.measure.value)
        if self.container is not None:
            object.__setattr__(self, "container", Container(self.container))


@dataclass(frozen=True, slots=True)
class Unparseable:
    text: str  # the text as given ("" for None)
    reason: ParseFail


def parse_size(text: str | None) -> PackageSize | Unparseable:
    """Read a size such as ``"16 oz"``, ``"12 x 12 fl oz"`` or ``"3 lb bag"``. Never raises."""
    original = "" if text is None else text
    normalized = _normalize(original)
    approximate = False
    lead = _APPROX.match(normalized)
    if lead:
        approximate = True
        normalized = normalized[lead.end() :]
    early = _reject_early(normalized)
    if early is not None:
        return Unparseable(original, early)
    for form, pattern in _FORMS:
        match = pattern.fullmatch(normalized)
        if match:
            built = _build(form, match, approximate)
            return built if isinstance(built, PackageSize) else Unparseable(original, built)
    return Unparseable(original, _why_not(normalized))


def format_size(s: PackageSize) -> str:
    """Write a size as text, e.g. ``"about 3 lb bag"``. ``parse_size`` reads it back exactly."""
    words = ["about"] if s.approximate else []
    words.append(size_label(s))
    if s.container is not None:
        words.append(s.container.value)
    return " ".join(words)


def size_label(s: PackageSize) -> str:
    """The size alone, without "about" or the container: ``"8 oz"``, ``"12 x 12 fl oz"``."""
    if s.measure is None:
        assert s.count is not None
        return f"{_number_text(s.count)} ct"
    if s.count is None:
        return f"{_number_text(s.measure.value)} {_unit_text(s.measure.unit, s.measure.value)}"
    inner = s.measure.value / s.count
    return f"{_number_text(s.count)} x {_number_text(inner)} {_unit_text(s.measure.unit, inner)}"


def _size_part(x: Fraction) -> Fraction:
    if x <= 0:
        raise ValueError("a package size must be more than zero")
    if x.numerator > MAX_SIZE_PART or x.denominator > MAX_SIZE_PART:
        raise ValueError("that package size is too large to be real")
    return x


# ---- reading ---------------------------------------------------------------------------------

_MASS_WORDS: dict[str, Unit] = {
    "oz": Unit.OZ,
    "ounce": Unit.OZ,
    "ounces": Unit.OZ,
    "lb": Unit.LB,
    "lbs": Unit.LB,
    "pound": Unit.LB,
    "pounds": Unit.LB,
    "g": Unit.G,
    "gram": Unit.G,
    "grams": Unit.G,
    "kg": Unit.KG,
    "kilogram": Unit.KG,
    "kilograms": Unit.KG,
}
_VOLUME_WORDS: dict[str, Unit] = {
    "fl oz": Unit.FL_OZ,
    "floz": Unit.FL_OZ,
    "fluid ounce": Unit.FL_OZ,
    "fluid ounces": Unit.FL_OZ,
    "ml": Unit.ML,
    "milliliter": Unit.ML,
    "milliliters": Unit.ML,
    "millilitre": Unit.ML,
    "millilitres": Unit.ML,
    "l": Unit.L,
    "liter": Unit.L,
    "liters": Unit.L,
    "litre": Unit.L,
    "litres": Unit.L,
    "gal": Unit.GAL,
    "gallon": Unit.GAL,
    "gallons": Unit.GAL,
    "qt": Unit.QT,
    "quart": Unit.QT,
    "quarts": Unit.QT,
    "pt": Unit.PT,
    "pint": Unit.PT,
    "pints": Unit.PT,
    "cup": Unit.CUP,
    "cups": Unit.CUP,
    "tbsp": Unit.TBSP,
    "tsp": Unit.TSP,
}
_MEASURE_WORDS = _MASS_WORDS | _VOLUME_WORDS
_COUNT_WORDS: dict[str, int] = {  # pieces per word
    "ct": 1,
    "count": 1,
    "each": 1,
    "ea": 1,
    "pk": 1,
    "pack": 1,
    "packs": 1,
    "piece": 1,
    "pieces": 1,
    "pc": 1,
    "pcs": 1,
    "dozen": 12,
    "dz": 12,
    "roll": 1,
    "rolls": 1,
    "can": 1,
    "cans": 1,
    "bottle": 1,
    "bottles": 1,
    "bag": 1,
    "bags": 1,
    "bunch": 1,
    "bunches": 1,
    "head": 1,
    "heads": 1,
    "ear": 1,
    "ears": 1,
    "loaf": 1,
    "loaves": 1,
    "stick": 1,
    "sticks": 1,
}
_CONTAINER_WORDS: dict[str, Container] = {c.value: c for c in Container} | {
    "pkg": Container.PACKAGE
}


def _words(words: Iterable[str]) -> str:
    return "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))


_NUM = r"\d+ \d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+"
_UNIT = _words([*_MEASURE_WORDS, *_COUNT_WORDS])
_TAIL = rf"(?:\s*(?P<container>{_words(_CONTAINER_WORDS)})\b)?"
_FORMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "multipack",
        re.compile(
            rf"(?P<n>{_NUM})\s*(?:x|(?:ct|pk|pack|count)\s*/)\s*"
            rf"(?P<inner>{_NUM})\s*(?P<unit>{_UNIT})\b{_TAIL}"
        ),
    ),
    (
        "compound",
        re.compile(
            rf"(?P<lb>{_NUM})\s*(?:lbs|lb|pounds|pound)\s*"
            rf"(?P<oz>{_NUM})\s*(?:ounces|ounce|oz)\b{_TAIL}"
        ),
    ),
    ("simple", re.compile(rf"(?P<n>{_NUM})\s*(?P<unit>{_UNIT})\b{_TAIL}")),
    ("bare", re.compile(r"(?P<bare>each|ea|per lb)\b")),
)
_DASHES = "".join(map(chr, range(0x2010, 0x2016)))  # Unicode hyphens and dashes
_MINUS_SIGN = chr(0x2212)
_FRACTION_SLASH = chr(0x2044)
_DIVISION_SLASH = chr(0x2215)
_MULTIPLICATION_SIGN = chr(0x00D7)
_APPROX = re.compile(r"(?:about|approximately|approx|average|avg)(?![a-z])\s*|~\s*")
_LONG_NUMBER = re.compile(r"\d{21,}")
_RANGE = re.compile(rf"(?:{_NUM})\s*(?:[-{_DASHES}]|\bto\b)\s*(?:{_NUM})")
_NEGATIVE = re.compile(rf"[-{_MINUS_SIGN}]\s*\.?\d")
_SEPARATOR = re.compile(rf"\s*(?:[,;/+&|\-{_DASHES}]|\b(?:and|or|plus)\b)?\s*")
_PARENS = re.compile(r"\([^()]*\)")
_STRAY_PERIOD = re.compile(r"\.(?!\d)")


def _normalize(text: str) -> str:
    # Space out vulgar fractions before NFKC, which alone would read "1" + "1/2" as "11/2".
    spaced = "".join(
        f" {unicodedata.normalize('NFKC', ch)} "
        if unicodedata.decomposition(ch).startswith("<fraction>")
        else ch
        for ch in text
    )
    s = unicodedata.normalize("NFKC", spaced)
    s = s.replace(_FRACTION_SLASH, "/").replace(_DIVISION_SLASH, "/")
    s = s.replace(_MULTIPLICATION_SIGN, "x").lower()
    while True:  # drop "( … )" groups, innermost first: "16 fl oz (473 mL)" -> "16 fl oz"
        without = _PARENS.sub(" ", s)
        if without == s:
            break
        s = without
    s = _STRAY_PERIOD.sub("", s)  # "16.9 fl. oz." -> "16.9 fl oz"
    return " ".join(s.split())


def _reject_early(s: str) -> ParseFail | None:
    if not s:
        return ParseFail.EMPTY
    if _LONG_NUMBER.search(s):
        return ParseFail.TOO_LARGE
    if _RANGE.search(s):
        return ParseFail.RANGE
    if _NEGATIVE.match(s):
        return ParseFail.NON_POSITIVE
    return None


def _build(form: str, m: re.Match[str], approximate: bool) -> PackageSize | ParseFail:
    count: Fraction | None = None
    measure: Quantity | None = None
    try:
        if form == "bare":
            if m.group("bare") == "per lb":
                measure = Quantity(Fraction(1), Unit.LB)
            else:
                count = Fraction(1)
        elif form == "compound":
            ounces = _number(m.group("lb")) * 16 + _number(m.group("oz"))
            measure = Quantity(ounces, Unit.OZ)
        else:
            n = _number(m.group("n"))
            if form == "multipack":
                inner = _number(m.group("inner"))
                if n <= 0 or inner <= 0:
                    return ParseFail.NON_POSITIVE
            else:
                inner = Fraction(1)
            word = m.group("unit")
            if word in _COUNT_WORDS:
                count = n * inner * _COUNT_WORDS[word]
            else:
                count = n if form == "multipack" else None
                measure = Quantity(n * inner, _MEASURE_WORDS[word])
    except ZeroDivisionError:
        return ParseFail.NON_POSITIVE
    if (count is not None and count <= 0) or (measure is not None and measure.value <= 0):
        return ParseFail.NON_POSITIVE
    container_word = m.groupdict().get("container")
    container = None if container_word is None else _CONTAINER_WORDS[container_word]
    try:
        return PackageSize(count, measure, approximate, container)
    except ValueError:
        return ParseFail.TOO_LARGE


def _number(text: str) -> Fraction:
    if " " in text:  # "1 1/2"
        whole, part = text.split(" ")
        return int(whole) + _number(part)
    if "/" in text:  # "3/4"; "1/0" raises ZeroDivisionError
        top, bottom = text.split("/")
        return Fraction(int(top), int(bottom))
    return Fraction(text)  # "16", "16.9", ".5"


def _longest_prefix(s: str) -> int | None:
    ends = [m.end() for _, pattern in _FORMS if (m := pattern.match(s))]
    return max(ends) if ends else None


def _why_not(s: str) -> ParseFail:
    end = _longest_prefix(s)
    if end is None:
        return ParseFail.UNKNOWN_UNIT
    rest = s[end:]
    separator = _SEPARATOR.match(rest)
    if separator:
        rest = rest[separator.end() :]
    if rest and _longest_prefix(rest) is not None:
        return ParseFail.MULTIPLE
    return ParseFail.TRAILING


# ---- writing ---------------------------------------------------------------------------------

_FRACTION_DENOMINATORS = frozenset({2, 4, 8, 16})  # written "1/2 gal", "1 1/4 lb"
_DECIMAL_SCALE = 10**6  # other values that end within 6 decimals are written "16.9"
_UNIT_TEXT: dict[Unit, str] = {
    Unit.G: "g",
    Unit.KG: "kg",
    Unit.OZ: "oz",
    Unit.LB: "lb",
    Unit.ML: "mL",
    Unit.L: "L",
    Unit.FL_OZ: "fl oz",
    Unit.TSP: "tsp",
    Unit.TBSP: "tbsp",
    Unit.CUP: "cup",
    Unit.PT: "pt",
    Unit.QT: "qt",
    Unit.GAL: "gal",
    Unit.EACH: "ct",
}


def _number_text(x: Fraction) -> str:
    if x.denominator == 1:
        return str(x.numerator)
    if x.denominator in _FRACTION_DENOMINATORS or _DECIMAL_SCALE % x.denominator:
        return to_mixed(x)
    whole, rest = divmod(x.numerator * (_DECIMAL_SCALE // x.denominator), _DECIMAL_SCALE)
    return f"{whole}.{rest:06d}".rstrip("0")


def _unit_text(unit: Unit, value: Fraction) -> str:
    if unit is Unit.CUP and value > 1:
        return "cups"
    return _UNIT_TEXT[unit]
