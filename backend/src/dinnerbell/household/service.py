from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.core.errors import AppError
from dinnerbell.household.models import MARKER_COLORS, Household, Member
from dinnerbell.household.schemas import MemberOut


def member_out(member: Member) -> MemberOut:
    return MemberOut.model_validate(
        {"id": member.id, "name": member.name, "marker_color": member.marker_color}
    )


async def household(session: AsyncSession) -> Household:
    row = await session.get(Household, 1)
    if row is None:  # the baseline migration always creates it
        raise AppError(500, "server_error", "Household settings are missing.")
    return row


async def active_members(session: AsyncSession) -> list[Member]:
    result = await session.scalars(
        select(Member).where(Member.archived_at.is_(None)).order_by(Member.sort, Member.created_at)
    )
    return list(result)


async def get_member(session: AsyncSession, member_id: str) -> Member:
    member = await session.get(Member, member_id)
    if member is None:
        raise AppError(404, "not_found", "That person isn't in this household.")
    return member


def next_marker_color(used: list[str]) -> str:
    for color in MARKER_COLORS:
        if color not in used:
            return color
    return MARKER_COLORS[len(used) % len(MARKER_COLORS)]


async def create_member(session: AsyncSession, name: str) -> Member:
    members = await active_members(session)
    member = Member(
        name=name,
        marker_color=next_marker_color([m.marker_color for m in members]),
        sort=len(members),
    )
    session.add(member)
    await session.flush()
    return member


async def archive_member(session: AsyncSession, member_id: str, now: datetime) -> Member:
    member = await get_member(session, member_id)
    member.archived_at = now
    return member


async def restore_member(session: AsyncSession, member_id: str) -> Member:
    member = await get_member(session, member_id)
    member.archived_at = None
    return member
