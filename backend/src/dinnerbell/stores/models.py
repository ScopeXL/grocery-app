"""Stores chosen by the household, and each store's walking order (docs/PLAN.md §5, §7.3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import UTCDateTime, new_id, utcnow


class Store(Base):
    """A store from Kroger's Locations API. The household's own record of where it shops."""

    __tablename__ = "stores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    location_id: Mapped[str] = mapped_column(String(16), unique=True)
    chain: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    address_line1: Mapped[str | None] = mapped_column(String(120), default=None)
    address_line2: Mapped[str | None] = mapped_column(String(120), default=None)
    city: Mapped[str | None] = mapped_column(String(80), default=None)
    state: Mapped[str | None] = mapped_column(String(16), default=None)
    zip_code: Mapped[str | None] = mapped_column(String(16), default=None)
    timezone: Mapped[str | None] = mapped_column(String(64), default=None)
    chain_domain: Mapped[str | None] = mapped_column(String(120), default=None)
    departments: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class StoreSection(Base):
    """One stop on the walk through a store: `aisle:12` or `cat:produce`, in walking order."""

    __tablename__ = "store_sections"
    __table_args__ = (UniqueConstraint("store_id", "key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    store_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(120))
    sort_index: Mapped[int] = mapped_column(Integer)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
