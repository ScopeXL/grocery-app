"""Kroger's data kept only as a cache, and the daily-limit counters (docs/PLAN.md §5, §7.4).

Neither table is household data: export skips both, and cache rows go once `expires_at`
passes (ADR 0016).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import UTCDateTime


class KrogerProductCache(Base):
    """One product at one store, exactly as Kroger returned it, until its headers say stop."""

    __tablename__ = "kroger_product_cache"

    product_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    location_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    cache_control_raw: Mapped[str] = mapped_column(String(200), default="")


class KrogerApiUsage(Base):
    """Calls per API bucket in Kroger's rolling 24 h window (usage.py)."""

    __tablename__ = "kroger_api_usage"

    api: Mapped[str] = mapped_column(String(16), primary_key=True)
    window_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    last_429_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    probe_backoff_s: Mapped[int | None] = mapped_column(Integer, default=None)
