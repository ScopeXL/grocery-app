"""Which occasion a main is planned for by default (ADR 0026): whatever it was last planned as,
else dinner. It comes from the plan history, so nothing is stored on the meal itself. A meal
removed from a plan doesn't count; past weeks do.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.planning.models import PlanMeal

DEFAULT_OCCASION = "dinner"


async def default_occasions(session: AsyncSession, main_ids: Iterable[str]) -> dict[str, str]:
    ids = sorted(set(main_ids))
    if not ids:
        return {}
    rows = await session.execute(
        select(PlanMeal.main_id, PlanMeal.occasion)
        .where(PlanMeal.main_id.in_(ids), PlanMeal.deleted_at.is_(None))
        .order_by(PlanMeal.created_at.desc(), PlanMeal.id.desc())
    )
    latest: dict[str, str] = {}
    for main_id, occasion in rows:
        latest.setdefault(main_id, occasion)
    return {main_id: latest.get(main_id, DEFAULT_OCCASION) for main_id in ids}
