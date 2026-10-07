"""Meals that use what you're buying (UX §4.4 "Uses what you're buying", PLAN §8.4).

Mains not on the plan yet, ranked by what they'd add to this week's total once the leftovers
of what's already being bought are used up. The ranking and the words are the domain's
(`domain.recommend`); this module gathers the plan, the candidates and today's prices.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy import select

from dinnerbell.catalog.models import Item
from dinnerbell.domain.recommend import Candidate, recommend
from dinnerbell.meals.models import Dish, DishItem
from dinnerbell.planning import listview
from dinnerbell.planning.schemas import SuggestionOut
from dinnerbell.state import AppState

LIMIT = 3


async def suggestions(state: AppState) -> list[SuggestionOut]:
    async with state.db.read() as db:
        data = await listview.load(db)
        if data.plan is None or not data.meals:
            return []
        planned = {meal.main_id for meal in data.meals}
        mains = [
            dish
            for dish in await db.scalars(
                select(Dish).where(Dish.role == "main", Dish.archived_at.is_(None))
            )
            if dish.id not in planned
        ]
        if not mains:
            return []
        lines: dict[str, list[DishItem]] = {dish.id: [] for dish in mains}
        for line in await db.scalars(
            select(DishItem).where(DishItem.dish_id.in_(lines)).order_by(DishItem.position)
        ):
            lines[line.dish_id].append(line)
        wanted = {line.item_id for group in lines.values() for line in group} - set(data.items)
        found = await db.scalars(select(Item).where(Item.id.in_(wanted)))
        rows = {row.id: row for row in found}
    # The candidates' items and prices join the plan's, so one Kroger batch covers both.
    data = replace(
        data,
        dishes={**data.dishes, **{dish.id: dish for dish in mains}},
        lines={**data.lines, **lines},
        items={**data.items, **rows},
    )
    live = await listview.fetch(state, data)
    plan = listview.plan_input(data, live)
    zone = state.settings.zone
    candidates = [
        Candidate(
            dish=listview.domain_dish(data, dish.id),
            role="main",
            archived=False,
            favorite=dish.favorite,
            last_made=dish.last_planned_at.astimezone(zone).date()
            if dish.last_planned_at
            else None,
        )
        for dish in mains
    ]
    out: list[SuggestionOut] = []
    for rec in recommend(plan, candidates, live.now, limit=LIMIT):
        ref = listview.dish_ref(state, data, rec.dish_id, live)
        out.append(
            SuggestionOut(
                dish_id=rec.dish_id,
                name=rec.name,
                photo_url=ref.photo_url,
                item_images=ref.item_images,
                text=rec.text,
                added_cents=rec.added_cents,
            )
        )
    return out
