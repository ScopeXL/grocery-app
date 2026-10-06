"""Items: the household's own names for what it buys (docs/PLAN.md §5).

An item may link to a Kroger product. Only the link and the facts the household confirmed
when linking are durable (ADR 0016): the package size (`size_text`, canonical, from
`domain.sizes.format_size`), whether Kroger sells it by unit or by weight, and an each-weight.
Descriptions, photos and prices always come from Kroger, live or from the expiring cache.
"""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import FractionText, UTCDateTime, new_id, utcnow


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    product_id: Mapped[str | None] = mapped_column(String(16), default=None, index=True)
    upc: Mapped[str | None] = mapped_column(String(16), default=None)
    size_text: Mapped[str | None] = mapped_column(String(80), default=None)
    size_source: Mapped[str] = mapped_column(String(16), default="parsed")  # parsed | household
    sold_by: Mapped[str | None] = mapped_column(String(8), default=None)  # UNIT | WEIGHT
    each_weight_lb: Mapped[Fraction | None] = mapped_column(FractionText(), default=None)
    is_staple: Mapped[bool] = mapped_column(Boolean, default=False)
    section_override_key: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
