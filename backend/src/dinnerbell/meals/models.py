"""Dishes (a Main or a Side), their item lines, and household photos (docs/PLAN.md §5)."""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import FractionText, UTCDateTime, new_id, utcnow


class Photo(Base):
    """A household photo, re-encoded as WebP without metadata (ADR 0020)."""

    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    webp: Mapped[bytes] = mapped_column(LargeBinary)  # at most 1600 px on the long side
    thumb: Mapped[bytes] = mapped_column(LargeBinary)  # at most 400 px
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Dish(Base):
    """A Main or a Side ("dish" in code; "Meal" is a planned Main with its Sides)."""

    __tablename__ = "dishes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(8))  # main | side
    occasions: Mapped[list[str]] = mapped_column(JSON, default=list)
    servings: Mapped[int | None] = mapped_column(Integer, default=None)
    photo_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("photos.id", ondelete="SET NULL"), default=None
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    recipe_url: Mapped[str | None] = mapped_column(String(500), default=None)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    last_planned_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)


class DishItem(Base):
    """How much of one item a dish uses, as the household entered it (never rounded)."""

    __tablename__ = "dish_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dish_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dishes.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id", ondelete="RESTRICT"), index=True
    )
    amount_kind: Mapped[str] = mapped_column(String(16))  # packages | measure | count
    amount: Mapped[Fraction] = mapped_column(FractionText())
    unit: Mapped[str | None] = mapped_column(String(8), default=None)
    position: Mapped[int] = mapped_column(Integer)
