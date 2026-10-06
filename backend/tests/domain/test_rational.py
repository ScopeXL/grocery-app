"""rational.py: exact numbers, and the two roundings (PLAN §8.1, §8.5 U4 and U5)."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Any, cast

import pytest

from dinnerbell.domain.rational import ceil_to, from_text, q, round_half_up, to_mixed, to_text


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (3, Fraction(3)),
        ("3/8", Fraction(3, 8)),
        ("0.375", Fraction(3, 8)),
        (" 2 ", Fraction(2)),
        ("-1/2", Fraction(-1, 2)),
        (".5", Fraction(1, 2)),
        (Decimal("1.15"), Fraction(23, 20)),
        (Fraction(6, 16), Fraction(3, 8)),
    ],
)
def test_q_reads_exact_values(given: int | str | Decimal | Fraction, expected: Fraction) -> None:
    assert q(given) == expected
    assert type(q(given)) is Fraction


def test_u5_q_refuses_floats_and_bools() -> None:
    for value in (0.5, 1.0, True, False):
        with pytest.raises(TypeError):
            q(cast(Any, value))


@pytest.mark.parametrize(
    "text", ["", "abc", "1e3", "1_000", "1/0", "1 1/2", "3/8 cup", "1" * 60, "nan", "inf"]
)
def test_q_refuses_text_it_cannot_read_exactly(text: str) -> None:
    with pytest.raises(ValueError, match=r"not a number|zero on the bottom"):
        q(text)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("1E+1000")])
def test_q_refuses_decimals_that_are_not_sensible_numbers(value: Decimal) -> None:
    with pytest.raises(ValueError):
        q(value)


def test_ceil_to_rounds_up_to_whole_steps() -> None:
    assert ceil_to(Fraction(21, 16), Fraction(1, 4)) == Fraction(3, 2)  # 21 oz -> 1 1/2 lb
    assert ceil_to(Fraction(1), Fraction(1, 4)) == Fraction(1)
    assert ceil_to(Fraction(1, 256), Fraction(1)) == Fraction(1)
    with pytest.raises(ValueError):
        ceil_to(Fraction(1), Fraction(0))


def test_u4_round_half_up_is_not_bankers_rounding() -> None:
    assert round_half_up(Fraction(897, 2)) == 449
    assert round(Fraction(897, 2)) == 448  # the trap: round() goes half to even
    assert round_half_up(Fraction(5, 2)) == 3
    assert round_half_up(Fraction(7, 3)) == 2
    assert round_half_up(Fraction(0)) == 0


def test_round_half_up_is_only_for_amounts_of_zero_or_more() -> None:
    with pytest.raises(ValueError):
        round_half_up(Fraction(-1, 2))


def test_storage_text_round_trips_and_is_canonical() -> None:
    for value in (Fraction(3, 8), Fraction(5), Fraction(-1, 2), Fraction(169, 10)):
        assert from_text(to_text(value)) == value
    assert to_text(Fraction(6, 16)) == "3/8"
    assert to_text(Fraction(5)) == "5"


@pytest.mark.parametrize("text", ["0.375", " 3/8", "3/0", "", "1 1/2", "+3"])
def test_from_text_reads_only_canonical_storage_text(text: str) -> None:
    with pytest.raises(ValueError):
        from_text(text)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Fraction(3, 2), "1 1/2"),
        (Fraction(3, 8), "3/8"),
        (Fraction(2), "2"),
        (Fraction(0), "0"),
        (Fraction(-3, 2), "-1 1/2"),
    ],
)
def test_to_mixed_writes_amounts_the_way_people_do(value: Fraction, text: str) -> None:
    assert to_mixed(value) == text
