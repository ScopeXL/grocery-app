"""sizes.py: the size parser, row by row from PLAN §8.3, and the writer."""

from __future__ import annotations

from typing import Any, cast

import pytest

from dinnerbell.domain.rational import q
from dinnerbell.domain.sizes import (
    Container,
    PackageSize,
    ParseFail,
    Unparseable,
    format_size,
    parse_size,
    size_label,
)
from dinnerbell.domain.units import Quantity, Unit

TIMES = chr(0x00D7)  # the multiplication sign, as some size strings use it


def measured(
    value: str, unit: Unit, *, approximate: bool = False, container: Container | None = None
) -> PackageSize:
    return PackageSize(None, Quantity(q(value), unit), approximate, container)


def counted(n: str, *, container: Container | None = None) -> PackageSize:
    return PackageSize(q(n), None, container=container)


def multipack(n: str, total: str, unit: Unit) -> PackageSize:
    return PackageSize(q(n), Quantity(q(total), unit))


PLAN_TABLE: list[tuple[str, PackageSize]] = [
    ("16 oz", measured("16", Unit.OZ)),
    ("2 lb", measured("2", Unit.LB)),
    ("0.75 lb", measured("3/4", Unit.LB)),
    ("6 ct", counted("6")),
    ("each", counted("1")),
    ("1 each", counted("1")),
    ("1 ea", counted("1")),
    ("1 dozen", counted("12")),
    ("1 gal", measured("1", Unit.GAL)),
    ("1/2 gal", measured("1/2", Unit.GAL)),
    ("½ gal", measured("1/2", Unit.GAL)),
    ("64 fl oz", measured("64", Unit.FL_OZ)),
    ("16.9 FL. OZ.", measured("169/10", Unit.FL_OZ)),
    ("12 x 12 fl oz", multipack("12", "144", Unit.FL_OZ)),
    ("6 ct / 16.9 fl oz", multipack("6", "507/5", Unit.FL_OZ)),
    ("8 x 1.5 oz", multipack("8", "12", Unit.OZ)),
    ("2 x 6 ct", counted("12")),
    ("3 lb bag", measured("3", Unit.LB, container=Container.BAG)),
    ("16 fl oz (473 mL)", measured("16", Unit.FL_OZ)),
    ("1 lb 8 oz", measured("24", Unit.OZ)),
    ("about 1.25 lb", measured("5/4", Unit.LB, approximate=True)),
    ("64 oz", measured("64", Unit.OZ)),  # always a weight; the household corrects juice
]

MORE_SIZES: list[tuple[str, PackageSize]] = [
    ("1½ lb", measured("3/2", Unit.LB)),  # not 11/2
    ("1 1/2 lb", measured("3/2", Unit.LB)),
    (f"12 {TIMES} 12 FL OZ", multipack("12", "144", Unit.FL_OZ)),
    ("12x12 fl oz", multipack("12", "144", Unit.FL_OZ)),
    ("6 pk / 12 fl oz", multipack("6", "72", Unit.FL_OZ)),
    ("2 x 1 dozen", counted("24")),
    ("16oz", measured("16", Unit.OZ)),
    (".5 lb", measured("1/2", Unit.LB)),
    ("approx. 2 lb", measured("2", Unit.LB, approximate=True)),
    ("~1 lb", measured("1", Unit.LB, approximate=True)),
    ("avg 12 oz", measured("12", Unit.OZ, approximate=True)),
    ("per lb", measured("1", Unit.LB)),
    ("16 OZ PKG", measured("16", Unit.OZ, container=Container.PACKAGE)),
    ("1 lb 8 oz bag", measured("24", Unit.OZ, container=Container.BAG)),
    ("6 ct box", counted("6", container=Container.BOX)),
    ("2 cups", measured("2", Unit.CUP)),
    ("1 L", measured("1", Unit.L)),
    ("500 mL", measured("500", Unit.ML)),
    ("1 qt", measured("1", Unit.QT)),
    ("1 pt", measured("1", Unit.PT)),  # a liquid pint
    ("4 rolls", counted("4")),
    ("1 bunch", counted("1")),
    ("2 dz", counted("24")),
    ("  16   oz  ", measured("16", Unit.OZ)),
]


@pytest.mark.parametrize(("text", "expected"), PLAN_TABLE + MORE_SIZES)
def test_parse_size_reads(text: str, expected: PackageSize) -> None:
    assert parse_size(text) == expected


PLAN_UNPARSEABLE: list[tuple[str | None, ParseFail]] = [
    ("Varies", ParseFail.UNKNOWN_UNIT),
    ("", ParseFail.EMPTY),
    (None, ParseFail.EMPTY),
    ("3-4 lb", ParseFail.RANGE),
    ("2 cu ft", ParseFail.UNKNOWN_UNIT),
    ("0 oz", ParseFail.NON_POSITIVE),
    ("12 oz, 2 ct", ParseFail.MULTIPLE),
]

MORE_UNPARSEABLE: list[tuple[str | None, ParseFail]] = [
    ("   ", ParseFail.EMPTY),
    ("(473 mL)", ParseFail.EMPTY),
    ("about", ParseFail.EMPTY),
    ("3 to 4 lb", ParseFail.RANGE),
    ("1.5 - 2 lb", ParseFail.RANGE),
    ("16 ozs", ParseFail.UNKNOWN_UNIT),
    ("lb", ParseFail.UNKNOWN_UNIT),
    ("1/0 lb", ParseFail.NON_POSITIVE),
    ("-1 lb", ParseFail.NON_POSITIVE),
    ("0 x 12 oz", ParseFail.NON_POSITIVE),
    ("2 x 0 ct", ParseFail.NON_POSITIVE),
    ("0 lb 0 oz", ParseFail.NON_POSITIVE),
    ("16 oz 16 oz", ParseFail.MULTIPLE),
    ("1 lb / 16 oz", ParseFail.MULTIPLE),
    ("16 oz bag of chips", ParseFail.TRAILING),
    ("16 oz,", ParseFail.TRAILING),
    ("per lb avg", ParseFail.TRAILING),
    ("1" * 30 + " oz", ParseFail.TOO_LARGE),
    ("9999999999 oz", ParseFail.TOO_LARGE),  # over the PackageSize limit
]


@pytest.mark.parametrize(("text", "reason"), PLAN_UNPARSEABLE + MORE_UNPARSEABLE)
def test_parse_size_explains_what_it_cannot_read(text: str | None, reason: ParseFail) -> None:
    assert parse_size(text) == Unparseable("" if text is None else text, reason)


@pytest.mark.parametrize(
    ("size", "text"),
    [
        (measured("3", Unit.LB, container=Container.BAG), "3 lb bag"),
        (measured("16", Unit.OZ), "16 oz"),
        (measured("5/4", Unit.LB, approximate=True), "about 1 1/4 lb"),
        (measured("1/2", Unit.GAL), "1/2 gal"),
        (measured("169/10", Unit.FL_OZ), "16.9 fl oz"),
        (measured("1/3", Unit.CUP), "1/3 cup"),
        (measured("2", Unit.CUP), "2 cups"),
        (measured("500", Unit.ML), "500 mL"),
        (measured("2", Unit.L), "2 L"),
        (counted("6"), "6 ct"),
        (counted("12", container=Container.BOX), "12 ct box"),
        (multipack("12", "144", Unit.FL_OZ), "12 x 12 fl oz"),
        (multipack("6", "507/5", Unit.FL_OZ), "6 x 16.9 fl oz"),
        (multipack("8", "12", Unit.OZ), "8 x 1 1/2 oz"),
    ],
)
def test_format_size_writes_text_that_reads_back(size: PackageSize, text: str) -> None:
    assert format_size(size) == text
    assert parse_size(text) == size


def test_size_label_leaves_out_about_and_the_container() -> None:
    assert size_label(measured("5/4", Unit.LB, approximate=True)) == "1 1/4 lb"
    assert size_label(measured("8", Unit.OZ, container=Container.BAG)) == "8 oz"
    assert size_label(multipack("12", "144", Unit.FL_OZ)) == "12 x 12 fl oz"


def test_container_plurals() -> None:
    assert [c.plural for c in (Container.BAG, Container.BOX, Container.POUCH)] == [
        "bags",
        "boxes",
        "pouches",
    ]


def test_a_package_size_is_always_real() -> None:
    with pytest.raises(ValueError, match="count, a measure or both"):
        PackageSize(None, None)
    with pytest.raises(ValueError, match="more than zero"):
        counted("0")
    with pytest.raises(ValueError, match="count belongs in count"):
        PackageSize(None, Quantity(q("6"), Unit.EACH))
    with pytest.raises(ValueError, match="too large"):
        counted("10000000000")
    with pytest.raises(TypeError):
        PackageSize(q("6"), None, cast(Any, 1))
