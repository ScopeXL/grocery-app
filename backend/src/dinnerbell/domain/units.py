"""Units, and exact conversion within one dimension (PLAN §8.1).

Weight and volume never convert into each other: a cup of shredded cheese has no fixed weight.
The constants are the exact legal definitions, so converting there and back is lossless.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from .rational import q


class Dimension(StrEnum):
    MASS = "mass"
    VOLUME = "volume"
    COUNT = "count"


class Unit(StrEnum):
    G = "g"
    KG = "kg"
    OZ = "oz"  # always weight; fluid ounces are FL_OZ
    LB = "lb"
    ML = "ml"
    L = "l"
    FL_OZ = "fl_oz"
    TSP = "tsp"
    TBSP = "tbsp"
    CUP = "cup"
    PT = "pt"  # a liquid pint
    QT = "qt"
    GAL = "gal"
    EACH = "each"

    @property
    def dimension(self) -> Dimension:
        return _UNITS[self][0]


class DimensionMismatch(ValueError):  # noqa: N818 - the name PLAN §8.2 uses
    """Raised when converting between weight, volume and counts, which never mix."""


@dataclass(frozen=True, slots=True)
class Quantity:
    value: Fraction
    unit: Unit

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", q(self.value))
        object.__setattr__(self, "unit", Unit(self.unit))

    @property
    def dimension(self) -> Dimension:
        return self.unit.dimension


def convert(x: Quantity, to: Unit) -> Quantity:
    """``x`` in unit ``to``, exactly. Raises DimensionMismatch across dimensions."""
    target = Unit(to)
    if x.unit is target:
        return x
    source_dimension, source_factor = _UNITS[x.unit]
    target_dimension, target_factor = _UNITS[target]
    if source_dimension is not target_dimension:
        raise DimensionMismatch(f"can't convert {x.unit.value} to {target.value}")
    return Quantity(x.value * source_factor / target_factor, target)


def ratio(a: Quantity, b: Quantity) -> Fraction:
    """How many ``b``s fit in ``a`` (``a / b``). Raises DimensionMismatch across dimensions."""
    return convert(a, b.unit).value / b.value


# Each unit's dimension and its size in the dimension's base unit (gram, milliliter, piece).
_GRAMS_PER_OZ = Fraction("28.349523125")
_ML_PER_FL_OZ = Fraction("29.5735295625")
_UNITS: dict[Unit, tuple[Dimension, Fraction]] = {
    Unit.G: (Dimension.MASS, Fraction(1)),
    Unit.KG: (Dimension.MASS, Fraction(1000)),
    Unit.OZ: (Dimension.MASS, _GRAMS_PER_OZ),
    Unit.LB: (Dimension.MASS, 16 * _GRAMS_PER_OZ),
    Unit.ML: (Dimension.VOLUME, Fraction(1)),
    Unit.L: (Dimension.VOLUME, Fraction(1000)),
    Unit.FL_OZ: (Dimension.VOLUME, _ML_PER_FL_OZ),
    Unit.TSP: (Dimension.VOLUME, _ML_PER_FL_OZ / 6),
    Unit.TBSP: (Dimension.VOLUME, _ML_PER_FL_OZ / 2),
    Unit.CUP: (Dimension.VOLUME, 8 * _ML_PER_FL_OZ),
    Unit.PT: (Dimension.VOLUME, 16 * _ML_PER_FL_OZ),
    Unit.QT: (Dimension.VOLUME, 32 * _ML_PER_FL_OZ),
    Unit.GAL: (Dimension.VOLUME, 128 * _ML_PER_FL_OZ),
    Unit.EACH: (Dimension.COUNT, Fraction(1)),
}
