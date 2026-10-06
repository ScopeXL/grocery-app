"""Column types shared by every feature: exact fractions, aware UTC datetimes, UUIDv7 ids."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from fractions import Fraction
from typing import Any

from sqlalchemy import DateTime, Dialect, String
from sqlalchemy.types import TypeDecorator


def new_id() -> str:
    """Time-ordered ids that a client could also generate (docs/PLAN.md §5)."""
    return str(uuid.uuid7())


class FractionText(TypeDecorator[Fraction]):
    """Exact quantities stored as canonical fraction text ("3/8", "2"). Floats are refused."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: Fraction | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if not isinstance(value, Fraction):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("FractionText columns only accept fractions.Fraction values")
        return str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Fraction | None:
        if value is None:
            return None
        return Fraction(str(value))


class UTCDateTime(TypeDecorator[datetime]):
    """Stores UTC; always returns timezone-aware datetimes (naive values are a bug)."""

    impl = DateTime(timezone=False)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime needs a timezone-aware datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)
