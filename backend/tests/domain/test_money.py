"""money.py: integer cents, promos and "about $N" (PLAN §8.4, §8.5 U3, U4 and the P cases)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any, cast

import pytest

from dinnerbell.domain.money import (
    PriceInfo,
    about_dollars,
    dollars_to_cents,
    dollars_to_exact_cents,
    effective_cents,
    promo_valid,
)
from tests.domain.builders import NOW


def price(
    regular: int | None = 349,
    promo: int | None = None,
    *,
    promo_from: datetime | None = None,
    promo_until: datetime | None = None,
) -> PriceInfo:
    return PriceInfo(
        regular=regular,
        promo=promo,
        promo_from=promo_from,
        promo_until=promo_until,
        fetched_at=NOW,
    )


def test_u3_dollars_become_exact_cents() -> None:
    assert dollars_to_cents(Decimal("1.15")) == 115
    assert dollars_to_cents("4.35") == 435
    assert int(float("1.15") * 100) == 114  # the trap the exact conversion avoids


@pytest.mark.parametrize(
    ("dollars", "cents"),
    [
        (None, None),
        (Decimal("0"), None),
        ("-1.00", None),
        (2, 200),  # JSON writes $2 as the int 2
        (Decimal("2.999"), 300),  # a sub-cent price rounds half-up
        ("0.005", 1),
    ],
)
def test_dollars_to_cents_edges(dollars: Decimal | int | str | None, cents: int | None) -> None:
    assert dollars_to_cents(dollars) == cents


def test_the_per_each_estimate_keeps_fractions_of_a_cent() -> None:
    assert dollars_to_exact_cents("0.0995") == Fraction(199, 20)
    assert dollars_to_exact_cents(Decimal("0.75")) == 75
    assert dollars_to_exact_cents(None) is None
    assert dollars_to_exact_cents("0") is None


def test_u4_about_dollars_rounds_half_up() -> None:
    assert about_dollars(14150) == 142
    assert about_dollars(14149) == 141
    assert about_dollars(0) == 0
    with pytest.raises(ValueError):
        about_dollars(-1)
    with pytest.raises(TypeError):
        about_dollars(cast(Any, True))


def test_p1_a_valid_promo_is_the_price() -> None:
    sale = price(promo=299)
    assert promo_valid(sale, NOW)
    assert effective_cents(sale, NOW) == 299


def test_p2_an_ended_promo_is_ignored() -> None:
    ended = price(promo=299, promo_until=datetime(2026, 10, 5, 4, 0, tzinfo=UTC))
    assert not promo_valid(ended, NOW)
    assert effective_cents(ended, NOW) == 349


def test_p3_a_promo_has_ended_at_its_end_instant() -> None:
    assert not promo_valid(price(promo=299, promo_until=NOW), NOW)
    assert promo_valid(price(promo=299, promo_until=NOW + timedelta(seconds=1)), NOW)


def test_p4_a_promo_that_has_not_started_is_ignored() -> None:
    later = price(promo=299, promo_from=datetime(2026, 10, 7, tzinfo=UTC))
    assert not promo_valid(later, NOW)
    assert promo_valid(price(promo=299, promo_from=NOW), NOW)  # starts now: half-open


@pytest.mark.parametrize("promo", [349, 400, 0, None])
def test_p5_a_promo_counts_only_below_the_regular_price(promo: int | None) -> None:
    assert not promo_valid(price(promo=promo), NOW)
    assert effective_cents(price(promo=promo), NOW) == 349


def test_p7_a_promo_alone_is_not_a_price() -> None:
    no_regular = price(regular=None, promo=299)
    assert not promo_valid(no_regular, NOW)
    with pytest.raises(ValueError):
        effective_cents(no_regular, NOW)


def test_now_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        promo_valid(price(promo=299), datetime(2026, 10, 6, 14, 0))  # noqa: DTZ001 - on purpose


def test_price_info_holds_only_sane_values() -> None:
    with pytest.raises(ValueError):
        PriceInfo(regular=100, fetched_at=datetime(2026, 10, 6))  # noqa: DTZ001 - on purpose
    with pytest.raises(ValueError):
        PriceInfo(regular=-1, fetched_at=NOW)
    with pytest.raises(TypeError):
        PriceInfo(regular=cast(Any, True), fetched_at=NOW)
    with pytest.raises(TypeError):
        PriceInfo(regular=cast(Any, Decimal("1.15")), fetched_at=NOW)
    with pytest.raises(ValueError):
        PriceInfo(regular=100, each_estimate=Fraction(-1), fetched_at=NOW)
    assert PriceInfo(regular=100, each_estimate=Fraction(75), fetched_at=NOW).each_estimate == 75
