"""This week's plan (docs/PLAN.md §5). Overrides never edit a dish; removals are soft (Undo)."""

from __future__ import annotations

from datetime import date, datetime
from fractions import Fraction

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import FractionText, UTCDateTime, new_id, utcnow


class Plan(Base):
    """Exactly one plan is active (the service keeps it so, under the write lock)."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | archived
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)


class PlanMeal(Base):
    """A Main on the plan, with its scale and an optional day (its Sides are rows below)."""

    __tablename__ = "plan_meals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    main_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dishes.id", ondelete="RESTRICT"), index=True
    )
    day: Mapped[date | None] = mapped_column(Date, default=None)  # a local date; None = any day
    occasion: Mapped[str] = mapped_column(String(16), default="dinner")
    scale: Mapped[Fraction] = mapped_column(FractionText(), default=Fraction(1))  # 1/2, 1 or 2
    position: Mapped[int] = mapped_column(Integer)
    added_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)


class PlanMealSide(Base):
    __tablename__ = "plan_meal_sides"

    plan_meal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plan_meals.id", ondelete="CASCADE"), primary_key=True
    )
    side_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dishes.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer)


class PlanExtra(Base):
    """Something added outside meals: an item (bought in its line's unit) or plain text."""

    __tablename__ = "plan_extras"
    __table_args__ = (CheckConstraint("(item_id IS NULL) != (text IS NULL)", name="item_or_text"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("items.id", ondelete="RESTRICT"), default=None, index=True
    )
    text: Mapped[str | None] = mapped_column(String(80), default=None)
    quantity: Mapped[Fraction] = mapped_column(FractionText(), default=Fraction(1))
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    added_by_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)


class PlanItemOverride(Base):
    """One item's changes for this plan only.

    * `have_it`: True "Have it", False "Need it", None not asked yet (staples start in the
      pantry check until answered).
    * `qty_delta`: what the household typed minus what the plan computed, in `qty_delta_unit`
      (`package`, `each` or `pound`), so a later meal still adds on top (PLAN §8.4).
    * `swap_*`: a product for this trip only, with the facts the household confirmed by choosing
      it, like an item's link (ADR 0016). "Always use this" re-links the item instead.
    """

    __tablename__ = "plan_item_overrides"

    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    have_it: Mapped[bool | None] = mapped_column(Boolean, default=None)
    qty_delta: Mapped[Fraction | None] = mapped_column(FractionText(), default=None)
    qty_delta_unit: Mapped[str | None] = mapped_column(String(8), default=None)
    swap_product_id: Mapped[str | None] = mapped_column(String(16), default=None)
    swap_upc: Mapped[str | None] = mapped_column(String(16), default=None)
    swap_size_text: Mapped[str | None] = mapped_column(String(80), default=None)
    swap_sold_by: Mapped[str | None] = mapped_column(String(8), default=None)  # UNIT | WEIGHT
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
