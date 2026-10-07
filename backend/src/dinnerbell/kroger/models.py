"""Kroger's data kept only as a cache, the daily-limit counters, and the household's Kroger
account link (docs/PLAN.md §5, §7.4, §7.5).

None of these tables is household data: export skips them all. Cache rows go once `expires_at`
passes (ADR 0016); the account's tokens are encrypted (§10.7).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import UTCDateTime, utcnow


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


class KrogerToken(Base):
    """Exactly one row (id = 1): the household's Kroger account, for sending lists to its cart.

    Both tokens are Fernet-encrypted under the `kroger-tokens-v1` key. `version` goes up on every
    change, so a refresh that raced a disconnect can't write tokens back (PLAN §7.5).
    """

    __tablename__ = "kroger_tokens"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # disconnected | connected | needs_reconnect
    status: Mapped[str] = mapped_column(String(16), default="disconnected")
    access_enc: Mapped[str | None] = mapped_column(Text, default=None)
    access_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    refresh_enc: Mapped[str | None] = mapped_column(Text, default=None)
    refresh_obtained_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    scope: Mapped[str | None] = mapped_column(String(200), default=None)
    connected_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    connected_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    version: Mapped[int] = mapped_column(Integer, default=0)


class KrogerOAuthState(Base):
    """One "Connect Kroger" in progress: single-use, for 10 minutes. The state is stored hashed;
    it is the only proof the callback needs, so a phone can finish in another browser."""

    __tablename__ = "kroger_oauth_states"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    code_verifier: Mapped[str] = mapped_column(String(128))
    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
