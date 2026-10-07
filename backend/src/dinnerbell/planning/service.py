"""Changing this week's plan: meals and their sides, usual sides, extras, overrides, a new week.

Everything here runs inside one write transaction and never calls Kroger: the router fetches
what a swap needs before the transaction opens (the write lock is not re-entrant).
Attribution comes from the signed-in device's member, never from the request body.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from fractions import Fraction

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.auth.models import Device
from dinnerbell.catalog.models import Item
from dinnerbell.catalog.service import parse_number
from dinnerbell.core.errors import AppError
from dinnerbell.domain.sizes import PackageSize, format_size, parse_size
from dinnerbell.household.models import Member
from dinnerbell.kroger.parse import Product, SoldBy
from dinnerbell.meals.models import Dish, DishPairing
from dinnerbell.planning.models import (
    Plan,
    PlanExtra,
    PlanItemOverride,
    PlanMeal,
    PlanMealSide,
)
from dinnerbell.planning.schemas import MealCreate, MealUpdate

USUAL_SIDES = 6
MAX_EXTRA = Fraction(99)  # packages or pounds; anything more is a typo
POUND_STEP = Fraction(1, 4)


# ---- the plan and who is changing it --------------------------------------------------------


async def active_plan(session: AsyncSession) -> Plan | None:
    return await session.scalar(
        select(Plan).where(Plan.status == "active").order_by(Plan.started_at.desc()).limit(1)
    )


async def ensure_plan(session: AsyncSession, now: datetime) -> Plan:
    """The active plan, started on the first change (one at a time, under the write lock)."""
    plan = await active_plan(session)
    if plan is None:
        plan = Plan(status="active", started_at=now)
        session.add(plan)
        await session.flush()
    return plan


async def require_plan(session: AsyncSession) -> Plan:
    plan = await active_plan(session)
    if plan is None:
        raise AppError(404, "plan_not_found", "Nothing is planned yet.")
    return plan


async def member_for(session: AsyncSession, device_id: str) -> str | None:
    """The member using this device right now, if they chose one and are still in the household."""
    return await session.scalar(
        select(Member.id)
        .join(Device, Device.member_id == Member.id)
        .where(Device.id == device_id, Member.archived_at.is_(None))
    )


# ---- planned meals ----------------------------------------------------------------------------


async def checked_dish(session: AsyncSession, dish_id: str, role: str) -> Dish:
    dish = await session.get(Dish, dish_id)
    if dish is None or dish.archived_at is not None:
        raise AppError(404, "dish_not_found", "That meal is gone. Choose another.")
    if dish.role != role:
        message = "Choose a Main here." if role == "main" else "Choose a Side here."
        raise AppError(422, "wrong_role", message)
    return dish


async def checked_sides(session: AsyncSession, side_ids: Sequence[str]) -> list[Dish]:
    return [await checked_dish(session, side_id, "side") for side_id in dict.fromkeys(side_ids)]


async def get_meal(session: AsyncSession, plan: Plan, meal_id: str) -> PlanMeal:
    meal = await session.get(PlanMeal, meal_id)
    if meal is None or meal.plan_id != plan.id:
        raise AppError(404, "meal_not_planned", "That meal isn't on this week's plan anymore.")
    return meal


async def add_meal(
    session: AsyncSession, plan: Plan, body: MealCreate, member_id: str | None, now: datetime
) -> PlanMeal:
    main = await checked_dish(session, body.main_id, "main")
    sides = await checked_sides(session, body.side_ids)
    last = await session.scalar(
        select(func.max(PlanMeal.position)).where(PlanMeal.plan_id == plan.id)
    )
    meal = PlanMeal(
        plan_id=plan.id,
        main_id=main.id,
        day=body.day,
        occasion=body.occasion,
        scale=Fraction(body.scale),
        position=0 if last is None else last + 1,
        added_by_member_id=member_id,
        created_at=now,
    )
    session.add(meal)
    await session.flush()
    write_sides(session, meal, sides)
    await record_pairings(session, main.id, [side.id for side in sides], now)
    for dish in (main, *sides):
        dish.last_planned_at = now
    return meal


async def update_meal(
    session: AsyncSession, meal: PlanMeal, body: MealUpdate, sent: set[str], now: datetime
) -> None:
    if body.main_id is not None and body.main_id != meal.main_id:
        main = await checked_dish(session, body.main_id, "main")
        meal.main_id = main.id
        main.last_planned_at = now
    if "day" in sent:
        meal.day = body.day
    if body.occasion is not None:
        meal.occasion = body.occasion
    if body.scale is not None:
        meal.scale = Fraction(body.scale)


async def set_sides(
    session: AsyncSession, meal: PlanMeal, side_ids: Sequence[str], now: datetime
) -> None:
    sides = await checked_sides(session, side_ids)
    before = set(
        await session.scalars(
            select(PlanMealSide.side_id).where(PlanMealSide.plan_meal_id == meal.id)
        )
    )
    await session.execute(delete(PlanMealSide).where(PlanMealSide.plan_meal_id == meal.id))
    await session.flush()
    write_sides(session, meal, sides)
    added = [side for side in sides if side.id not in before]
    await record_pairings(session, meal.main_id, [side.id for side in added], now)
    for side in added:
        side.last_planned_at = now


def write_sides(session: AsyncSession, meal: PlanMeal, sides: Sequence[Dish]) -> None:
    for position, side in enumerate(sides):
        session.add(PlanMealSide(plan_meal_id=meal.id, side_id=side.id, position=position))


# ---- usual sides ------------------------------------------------------------------------------


async def record_pairings(
    session: AsyncSession, main_id: str, side_ids: Sequence[str], now: datetime
) -> None:
    """Choosing a Side with a Main teaches Dinner Bell its usual sides."""
    for side_id in side_ids:
        pairing = await session.get(DishPairing, (main_id, side_id))
        if pairing is None:
            pairing = DishPairing(
                main_id=main_id, side_id=side_id, times_chosen=0, pinned=False, hidden=False
            )
            session.add(pairing)
        pairing.times_chosen += 1
        pairing.last_chosen_at = now


async def usual_sides(session: AsyncSession, main_id: str) -> list[tuple[Dish, DishPairing]]:
    """Pinned sides first, then the most often and most recently chosen; hidden ones never."""
    rows = await session.execute(
        select(Dish, DishPairing)
        .join(DishPairing, DishPairing.side_id == Dish.id)
        .where(
            DishPairing.main_id == main_id,
            DishPairing.hidden.is_(False),
            or_(DishPairing.pinned.is_(True), DishPairing.times_chosen > 0),
            Dish.archived_at.is_(None),
            Dish.role == "side",
        )
    )
    found = [(dish, pairing) for dish, pairing in rows]
    found.sort(
        key=lambda pair: (
            not pair[1].pinned,
            -pair[1].times_chosen,
            -(pair[1].last_chosen_at.timestamp() if pair[1].last_chosen_at else 0),
            pair[0].name.casefold(),
            pair[0].id,
        )
    )
    return found[:USUAL_SIDES]


async def set_usual_sides(session: AsyncSession, main_id: str, side_ids: Sequence[str]) -> None:
    await checked_dish(session, main_id, "main")
    sides = await checked_sides(session, side_ids)
    chosen = {side.id for side in sides}
    for _dish, pairing in await usual_sides(session, main_id):
        if pairing.side_id not in chosen:
            pairing.pinned, pairing.hidden = False, True
    for side in sides:
        pairing = await session.get(DishPairing, (main_id, side.id))
        if pairing is None:
            pairing = DishPairing(main_id=main_id, side_id=side.id, times_chosen=0)
            session.add(pairing)
        pairing.pinned, pairing.hidden = True, False


# ---- extras -----------------------------------------------------------------------------------


def check_steps(value: Fraction, *, by_weight: bool) -> None:
    """Whole packages or pieces; quarter pounds for something sold by the pound (PLAN §8.8)."""
    step = POUND_STEP if by_weight else Fraction(1)
    if (value / step).denominator != 1:
        message = (
            "Choose pounds in quarters, like 1 1/4." if by_weight else "Choose a whole number."
        )
        raise AppError(422, "quantity_invalid", message)


def extra_quantity(text: str, *, by_weight: bool) -> Fraction:
    value = parse_number(text)
    if value is None or not 0 < value <= MAX_EXTRA:
        raise AppError(422, "quantity_invalid", "Choose an amount between 1/4 and 99.")
    check_steps(value, by_weight=by_weight)
    return value


async def sold_by_weight(session: AsyncSession, plan: Plan, row: Item) -> bool:
    """Whether the product this plan buys for the item is priced per pound."""
    override = await session.get(PlanItemOverride, (plan.id, row.id))
    swapped = override is not None and override.swap_product_id is not None
    sold_by = override.swap_sold_by if override is not None and swapped else row.sold_by
    return sold_by == "WEIGHT"


async def get_extra(session: AsyncSession, plan: Plan, extra_id: str) -> PlanExtra:
    extra = await session.get(PlanExtra, extra_id)
    if extra is None or extra.plan_id != plan.id:
        raise AppError(404, "extra_not_found", "That extra isn't on this week's list anymore.")
    return extra


async def add_extra(
    session: AsyncSession,
    plan: Plan,
    *,
    item_id: str | None,
    text: str | None,
    quantity: str,
    note: str | None,
    member_id: str | None,
    now: datetime,
) -> PlanExtra:
    """Adding what's already an extra adds to it; adding an item clears its "Have it"."""
    statement = select(PlanExtra).where(
        PlanExtra.plan_id == plan.id, PlanExtra.deleted_at.is_(None)
    )
    if item_id is not None:
        row = await session.get(Item, item_id)
        if row is None or row.archived_at is not None:
            raise AppError(404, "item_not_found", "That item is gone. Add it again.")
        amount = extra_quantity(quantity, by_weight=await sold_by_weight(session, plan, row))
        existing = await session.scalar(statement.where(PlanExtra.item_id == item_id))
        override = await session.get(PlanItemOverride, (plan.id, item_id))
        if override is not None and override.have_it:
            override.have_it = False
    else:
        assert text is not None
        amount = extra_quantity(quantity, by_weight=False)
        existing = next(
            (
                extra
                for extra in await session.scalars(statement.where(PlanExtra.text.is_not(None)))
                if (extra.text or "").casefold() == text.casefold()
            ),
            None,
        )
    if existing is not None:
        existing.quantity = min(existing.quantity + amount, MAX_EXTRA)
        if note:
            existing.note = note
        return existing
    extra = PlanExtra(
        plan_id=plan.id,
        item_id=item_id,
        text=text,
        quantity=amount,
        note=note or None,
        added_by_member_id=member_id,
        created_at=now,
    )
    session.add(extra)
    await session.flush()
    return extra


# ---- overrides --------------------------------------------------------------------------------


async def override_for(session: AsyncSession, plan: Plan, item_id: str) -> PlanItemOverride:
    row = await session.get(Item, item_id)
    if row is None:
        raise AppError(404, "item_not_found", "That item couldn't be found.")
    override = await session.get(PlanItemOverride, (plan.id, item_id))
    if override is None:
        override = PlanItemOverride(plan_id=plan.id, item_id=item_id)
        session.add(override)
    return override


def set_swap(override: PlanItemOverride, product: Product | None) -> None:
    """Record the product chosen for this trip, with the facts the household confirmed."""
    override.qty_delta = override.qty_delta_unit = None  # the quantity is worked out afresh
    if product is None:
        override.swap_product_id = override.swap_upc = None
        override.swap_size_text = override.swap_sold_by = None
        return
    size = parse_size(product.size)
    override.swap_product_id = product.product_id
    override.swap_upc = product.upc
    override.swap_size_text = format_size(size) if isinstance(size, PackageSize) else None
    override.swap_sold_by = (product.sold_by or SoldBy.UNIT).value


async def drop_if_empty(session: AsyncSession, override: PlanItemOverride) -> None:
    if override.have_it is None and override.qty_delta is None and override.swap_product_id is None:
        await session.delete(override)


# ---- a new week -------------------------------------------------------------------------------


async def has_content(session: AsyncSession, plan: Plan) -> bool:
    for model in (PlanMeal, PlanExtra):
        found = await session.scalar(
            select(model.id).where(model.plan_id == plan.id, model.deleted_at.is_(None)).limit(1)
        )
        if found is not None:
            return True
    return False


async def new_week(session: AsyncSession, now: datetime) -> Plan | None:
    """Put this week's plan away; the next change starts a fresh one. None if nothing to do."""
    plan = await active_plan(session)
    if plan is None:
        return None
    plan.status, plan.archived_at = "archived", now
    return plan


async def undo_new_week(session: AsyncSession, plan_id: str) -> None:
    previous = await session.get(Plan, plan_id)
    if previous is None or previous.status != "archived":
        raise AppError(404, "plan_not_found", "That week can't be brought back.")
    current = await active_plan(session)
    if current is not None:
        if await has_content(session, current):
            raise AppError(
                409, "week_started", "The new week already has meals. Remove them first."
            )
        await session.delete(current)
        await session.flush()
    previous.status, previous.archived_at = "active", None
