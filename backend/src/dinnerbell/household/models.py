"""Household-wide settings, app metadata and members (docs/PLAN.md §5)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import UTCDateTime, new_id, utcnow

MARKER_COLORS = ("basil", "tomato", "carrot", "eggplant", "beet", "olive", "cocoa", "plum")


class Household(Base):
    """Exactly one row (id = 1): the household's own settings."""

    __tablename__ = "household"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(80), default="Our household")
    active_store_id: Mapped[str | None] = mapped_column(String(36), default=None)
    default_cart_modality: Mapped[str] = mapped_column(String(16), default="PICKUP")
    price_max_age_minutes: Mapped[int] = mapped_column(Integer, default=120)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class AppMeta(Base):
    """Exactly one row (id = 1): values the app itself manages across restarts."""

    __tablename__ = "app_meta"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    auth_epoch: Mapped[int] = mapped_column(Integer, default=1)
    password_fp: Mapped[str | None] = mapped_column(String(64), default=None)
    secret_key_check: Mapped[str | None] = mapped_column(String(64), default=None)
    last_boot_version: Mapped[str | None] = mapped_column(String(32), default=None)


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(40))
    marker_color: Mapped[str] = mapped_column(String(16))
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
