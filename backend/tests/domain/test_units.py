"""units.py: exact conversion within a dimension, never across (PLAN §8.1, §8.5 U1 and U2)."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, cast

import pytest

from dinnerbell.domain.units import Dimension, DimensionMismatch, Quantity, Unit, convert, ratio


def qty(value: str, unit: Unit) -> Quantity:
    return Quantity(Fraction(value), unit)


def test_u1_conversions_are_exact() -> None:
    assert convert(qty("1", Unit.LB), Unit.G).value == Fraction(45359237, 100000)
    assert convert(qty("1", Unit.CUP), Unit.ML).value == Fraction(473176473, 2000000)


def test_u2_spoons_compare_exactly_and_weight_never_becomes_volume() -> None:
    assert convert(qty("3", Unit.TSP), Unit.TBSP) == qty("1", Unit.TBSP)
    assert ratio(qty("3", Unit.TSP), qty("1", Unit.TBSP)) == 1
    with pytest.raises(DimensionMismatch):
        convert(qty("1", Unit.OZ), Unit.FL_OZ)
    assert issubclass(DimensionMismatch, ValueError)


@pytest.mark.parametrize(
    ("given", "to", "expected"),
    [
        (qty("1", Unit.LB), Unit.OZ, Fraction(16)),
        (qty("1", Unit.KG), Unit.G, Fraction(1000)),
        (qty("1", Unit.GAL), Unit.FL_OZ, Fraction(128)),
        (qty("1", Unit.GAL), Unit.CUP, Fraction(16)),
        (qty("1", Unit.QT), Unit.CUP, Fraction(4)),
        (qty("1", Unit.PT), Unit.CUP, Fraction(2)),
        (qty("1", Unit.CUP), Unit.TBSP, Fraction(16)),
        (qty("1", Unit.TBSP), Unit.TSP, Fraction(3)),
        (qty("1", Unit.L), Unit.ML, Fraction(1000)),
        (qty("3", Unit.EACH), Unit.EACH, Fraction(3)),
    ],
)
def test_the_unit_table(given: Quantity, to: Unit, expected: Fraction) -> None:
    assert convert(given, to).value == expected


def test_every_unit_has_one_dimension() -> None:
    assert {u for u in Unit if u.dimension is Dimension.MASS} == {
        Unit.G,
        Unit.KG,
        Unit.OZ,
        Unit.LB,
    }
    assert {u for u in Unit if u.dimension is Dimension.COUNT} == {Unit.EACH}
    assert qty("1", Unit.FL_OZ).dimension is Dimension.VOLUME


def test_counts_never_convert_to_weight_or_volume() -> None:
    with pytest.raises(DimensionMismatch):
        convert(qty("2", Unit.EACH), Unit.G)
    with pytest.raises(DimensionMismatch):
        ratio(qty("1", Unit.CUP), qty("1", Unit.EACH))


def test_quantity_is_exact_and_reads_unit_names() -> None:
    assert Quantity(Fraction(1), cast(Any, "oz")).unit is Unit.OZ
    with pytest.raises(ValueError):
        Quantity(Fraction(1), cast(Any, "cu ft"))
    with pytest.raises(TypeError):
        Quantity(cast(Any, 1.5), Unit.OZ)
