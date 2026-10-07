"""Signed-in devices, and the one-time codes that add a phone (docs/adr/0004)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from dinnerbell.db.base import Base
from dinnerbell.db.types import UTCDateTime, new_id, utcnow


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    label: Mapped[str] = mapped_column(String(80))
    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)


class JoinCode(Base):
    """A code a signed-in phone shows (as a QR code, and in letters) so another phone can sign
    in without the password: single-use, for 10 minutes, stored hashed (PLAN §10.2)."""

    __tablename__ = "join_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_by_device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    used_by_device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="SET NULL"), default=None
    )
