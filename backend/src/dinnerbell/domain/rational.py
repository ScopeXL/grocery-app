"""Exact numbers for quantities and money (PLAN §8.1, ADR 0007).

Every quantity is a ``Fraction``. Floats are refused everywhere: they can't hold 1.1 oz or 1/3 cup
exactly, and three meals of 1.1 oz from a 3.3 oz package would buy two packages instead of one.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal
from fractions import Fraction
from typing import cast

_HALF = Fraction(1, 2)
_MAX_TEXT = 50  # longest number text q() reads (API input), so a huge number can't be built
_MAX_DECIMAL_DIGITS = 40
_NUMBER_TEXT = re.compile(r"[+-]?(?:\d+/\d+|\d+(?:\.\d+)?|\.\d+)")
_STORED_TEXT = re.compile(r"-?\d+(?:/\d+)?")


def q(x: int | str | Decimal | Fraction) -> Fraction:
    """Return ``x`` as an exact Fraction. Every quantity constructor goes through here.

    Reads ints, Fractions, finite Decimals, and text such as ``"3/8"``, ``"0.375"`` or ``"-2"``.
    Raises TypeError for a float or a bool, and ValueError for text it can't read.
    """
    value = cast(object, x)  # check the runtime type, whatever the annotation says
    if isinstance(value, bool | float):
        raise TypeError(f"{type(value).__name__} is not exact; use int, str, Decimal or Fraction")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Decimal):
        return _from_decimal(value)
    if isinstance(value, str):
        return _from_text(value)
    raise TypeError(f"{type(value).__name__} is not a number")


def ceil_to(x: Fraction, step: Fraction) -> Fraction:
    """Round ``x`` up to a whole number of ``step``s: ``ceil(x / step) * step``."""
    value, size = q(x), q(step)
    if size <= 0:
        raise ValueError("step must be more than zero")
    return math.ceil(value / size) * size


def round_half_up(x: Fraction) -> int:
    """``floor(x + 1/2)`` for ``x >= 0``. Python's ``round()`` rounds half to even; never use it."""
    value = q(x)
    if value < 0:
        raise ValueError("round_half_up is only for amounts of zero or more")
    return math.floor(value + _HALF)


def to_text(x: Fraction) -> str:
    """Canonical storage text: ``"3/8"``, ``"5"``, ``"-1/2"``."""
    return str(q(x))


def from_text(s: str) -> Fraction:
    """Read canonical storage text written by ``to_text``. Anything else raises ValueError."""
    if not _STORED_TEXT.fullmatch(s):
        raise ValueError(f"not a stored fraction: {s[:_MAX_TEXT]!r}")
    try:
        return Fraction(s)
    except ZeroDivisionError:
        raise ValueError("a stored fraction can't have zero on the bottom") from None


def to_mixed(x: Fraction) -> str:
    """How people write an amount: ``"1 1/2"``, ``"3/8"``, ``"2"``."""
    value = q(x)
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole, rest = divmod(value.numerator, value.denominator)
    if rest == 0:
        return f"{sign}{whole}"
    part = f"{rest}/{value.denominator}"
    return f"{sign}{whole} {part}" if whole else f"{sign}{part}"


def _from_decimal(value: Decimal) -> Fraction:
    if not value.is_finite():
        raise ValueError("not a finite number")
    parts = value.as_tuple()
    exponent = parts.exponent
    if (
        not isinstance(exponent, int)
        or abs(exponent) > _MAX_DECIMAL_DIGITS
        or len(parts.digits) > _MAX_DECIMAL_DIGITS
    ):
        raise ValueError("number is out of range")
    return Fraction(value)


def _from_text(text: str) -> Fraction:
    stripped = text.strip()
    if len(stripped) > _MAX_TEXT or not _NUMBER_TEXT.fullmatch(stripped):
        raise ValueError(f"not a number: {text[:_MAX_TEXT]!r}")
    try:
        return Fraction(stripped)
    except ZeroDivisionError:
        raise ValueError("a fraction can't have zero on the bottom") from None
