"""This week's plan, its extras and per-plan changes, and each Main's usual sides.

Every change answers with the whole plan (`PlanOut`, with `changed` naming what was added), so
the screen updates from the response. Kroger is called only outside write transactions.
"""

from __future__ import annotations

from fractions import Fraction

from fastapi import APIRouter

from dinnerbell.auth.deps import SessionDep
from dinnerbell.catalog import service as items
from dinnerbell.catalog.mapping import price_info
from dinnerbell.catalog.models import Item
from dinnerbell.core.errors import AppError
from dinnerbell.domain import models as domain
from dinnerbell.domain.listbuild import unit_price
from dinnerbell.domain.rational import to_text
from dinnerbell.kroger.client import KrogerError
from dinnerbell.kroger.parse import Product
from dinnerbell.meals.models import Dish, DishPairing
from dinnerbell.meals.service import photo_url
from dinnerbell.planning import listview, service, suggest
from dinnerbell.planning.models import PlanItemOverride
from dinnerbell.planning.schemas import (
    AlternativeOut,
    AlternativesOut,
    ExtraCreate,
    ExtraUpdate,
    ItemOverrideIn,
    MealCreate,
    MealUpdate,
    NewWeekUndo,
    PlanOut,
    RepeatIn,
    SidesIn,
    SuggestionOut,
    UsualSideOut,
    UsualSidesIn,
)
from dinnerbell.shopping.models import Trip
from dinnerbell.state import AppState, StateDep

router = APIRouter(prefix="/api", tags=["planning"])
PLAN_CHANGED = "plan.changed"
SEARCH_LIMIT = 20


@router.get("/plan")
async def get_plan(state: StateDep, session: SessionDep) -> PlanOut:
    return await listview.plan_view(state)


@router.get("/plan/recommendations")
async def recommendations(state: StateDep, session: SessionDep) -> list[SuggestionOut]:
    """Mains that use what this week's list already buys (UX §4.4), best first."""
    return await suggest.suggestions(state)


# ---- planned meals ----------------------------------------------------------------------------


@router.post("/plan/meals", status_code=201)
async def add_meal(body: MealCreate, state: StateDep, session: SessionDep) -> PlanOut:
    now = state.clock.now()
    async with state.db.write() as tx:
        plan = await service.ensure_plan(tx.session, now)
        member_id = await service.member_for(tx.session, session.device_id)
        meal = await service.add_meal(tx.session, plan, body, member_id, now)
        tx.publish(PLAN_CHANGED)
        tx.publish("dishes.changed", {"id": body.main_id})  # usual sides were learned
        meal_id = meal.id
    return await listview.plan_view(state, changed=meal_id)


@router.patch("/plan/meals/{meal_id}")
async def update_meal(
    meal_id: str, body: MealUpdate, state: StateDep, session: SessionDep
) -> PlanOut:
    async with state.db.write() as tx:
        plan = await service.require_plan(tx.session)
        meal = await service.get_meal(tx.session, plan, meal_id)
        await service.update_meal(tx.session, meal, body, body.model_fields_set, state.clock.now())
        tx.publish(PLAN_CHANGED)
    return await listview.plan_view(state, changed=meal_id)


@router.put("/plan/meals/{meal_id}/sides")
async def set_sides(meal_id: str, body: SidesIn, state: StateDep, session: SessionDep) -> PlanOut:
    async with state.db.write() as tx:
        plan = await service.require_plan(tx.session)
        meal = await service.get_meal(tx.session, plan, meal_id)
        await service.set_sides(tx.session, meal, body.side_ids, state.clock.now())
        tx.publish(PLAN_CHANGED)
        tx.publish("dishes.changed", {"id": meal.main_id})
    return await listview.plan_view(state, changed=meal_id)


@router.delete("/plan/meals/{meal_id}")
async def remove_meal(meal_id: str, state: StateDep, session: SessionDep) -> PlanOut:
    async with state.db.write() as tx:
        plan = await service.require_plan(tx.session)
        meal = await service.get_meal(tx.session, plan, meal_id)
        meal.deleted_at = meal.deleted_at or state.clock.now()
        tx.publish(PLAN_CHANGED)
    return await listview.plan_view(state, changed=meal_id)


@router.post("/plan/meals/{meal_id}/restore")
async def restore_meal(meal_id: str, state: StateDep, session: SessionDep) -> PlanOut:
    async with state.db.write() as tx:
        plan = await service.require_plan(tx.session)
        meal = await service.get_meal(tx.session, plan, meal_id)
        meal.deleted_at = None
        tx.publish(PLAN_CHANGED)
    return await listview.plan_view(state, changed=meal_id)


# ---- extras -----------------------------------------------------------------------------------


@router.post("/plan/extras", status_code=201)
async def add_extra(body: ExtraCreate, state: StateDep, session: SessionDep) -> PlanOut:
    now = state.clock.now()
    async with state.db.write() as tx:
        plan = await service.ensure_plan(tx.session, now)
        extra = await service.add_extra(
            tx.session,
            plan,
            item_id=body.item_id,
            text=body.text,
            quantity=body.quantity,
            note=body.note,
            member_id=await service.member_for(tx.session, session.device_id),
            now=now,
        )
        tx.publish(PLAN_CHANGED)
        extra_id = extra.id
    return await listview.plan_view(state, changed=extra_id)


@router.patch("/plan/extras/{extra_id}")
async def update_extra(
    extra_id: str, body: ExtraUpdate, state: StateDep, session: SessionDep
) -> PlanOut:
    async with state.db.write() as tx:
        plan = await service.require_plan(tx.session)
        extra = await service.get_extra(tx.session, plan, extra_id)
        if body.quantity is not None:
            row = await tx.session.get(Item, extra.item_id) if extra.item_id else None
            by_weight = row is not None and await service.sold_by_weight(tx.session, plan, row)
            extra.quantity = service.extra_quantity(body.quantity, by_weight=by_weight)
        if "note" in body.model_fields_set:
            extra.note = body.note or None
        tx.publish(PLAN_CHANGED)
    return await listview.plan_view(state, changed=extra_id)


@router.delete("/plan/extras/{extra_id}")
async def remove_extra(extra_id: str, state: StateDep, session: SessionDep) -> PlanOut:
    async with state.db.write() as tx:
        plan = await service.require_plan(tx.session)
        extra = await service.get_extra(tx.session, plan, extra_id)
        extra.deleted_at = extra.deleted_at or state.clock.now()
        tx.publish(PLAN_CHANGED)
    return await listview.plan_view(state, changed=extra_id)


@router.post("/plan/extras/{extra_id}/restore")
async def restore_extra(extra_id: str, state: StateDep, session: SessionDep) -> PlanOut:
    async with state.db.write() as tx:
        plan = await service.require_plan(tx.session)
        extra = await service.get_extra(tx.session, plan, extra_id)
        extra.deleted_at = None
        tx.publish(PLAN_CHANGED)
    return await listview.plan_view(state, changed=extra_id)


# ---- one line's changes -----------------------------------------------------------------------


@router.put("/plan/items/{item_id}")
async def change_item(
    item_id: str, body: ItemOverrideIn, state: StateDep, session: SessionDep
) -> PlanOut:
    sent = body.model_fields_set
    product: Product | None = None
    if "swap_product_id" in sent and body.swap_product_id:
        product = await items.linked_product(state, body.swap_product_id)
    delta: tuple[domain.PurchaseUnit, Fraction] | None = None
    if "quantity" in sent and body.quantity is not None:
        delta = await _quantity_change(state, item_id, body)
    async with state.db.write() as tx:
        plan = await service.ensure_plan(tx.session, state.clock.now())
        override = await service.override_for(tx.session, plan, item_id)
        if "have_it" in sent:
            override.have_it = body.have_it
        if "quantity" in sent:
            if delta is None:
                override.qty_delta = override.qty_delta_unit = None
            else:
                unit, change = delta
                override.qty_delta = change or None
                override.qty_delta_unit = unit.value if change else None
        if "swap_product_id" in sent:
            if body.always and product is not None:
                row = await items.get_item(tx.session, item_id)
                items.link(row, product)
                service.set_swap(override, None)
                tx.publish("items.changed", {"id": item_id})
            else:
                service.set_swap(override, product)
        await service.drop_if_empty(tx.session, override)
        tx.publish(PLAN_CHANGED)
    return await listview.plan_view(state, changed=item_id)


async def _quantity_change(
    state: AppState, item_id: str, body: ItemOverrideIn
) -> tuple[domain.PurchaseUnit, Fraction]:
    """The typed quantity minus what the plan computes now, in the line's unit."""
    assert body.quantity is not None
    typed = items.parse_number(body.quantity)
    if typed is None or typed < 0 or typed > service.MAX_EXTRA:
        raise AppError(422, "quantity_invalid", "Choose an amount between 0 and 99.")
    _data, _live, built = await listview.build(state)
    line = next((line for line in built.lines if line.item_id == item_id), None)
    if line is None:
        raise AppError(404, "line_not_found", "That item isn't on the list anymore.")
    if body.unit is not None and body.unit != line.unit.value:
        raise AppError(409, "list_changed", "The list just changed. Check the amount again.")
    service.check_steps(typed, by_weight=line.unit is domain.PurchaseUnit.POUND)
    return line.unit, typed - line.computed


@router.get("/plan/items/{item_id}/alternatives")
async def alternatives(item_id: str, state: StateDep, session: SessionDep) -> AlternativesOut:
    """Other products for a line, each with its price per ounce (or pound, or piece)."""
    store = await items.require_store(state)
    async with state.db.read() as db:
        row = await items.get_item(db, item_id)
        plan = await service.active_plan(db)
        override = await db.get(PlanItemOverride, (plan.id, item_id)) if plan else None
    words = row.name.split()
    if len("".join(words)) < 3:
        raise AppError(422, "term_too_short", "Search for it by name instead.")
    current_id = (override.swap_product_id if override else None) or row.product_id
    found = await state.catalog.search(
        " ".join(words[: items.MAX_TERM_WORDS]), store.location_id, limit=SEARCH_LIMIT
    )
    if current_id and all(product.product_id != current_id for product in found):
        try:
            current = await state.catalog.product(current_id, store.location_id)
        except KrogerError:
            current = None
        if current is not None:
            found = [current, *found]
    zone, now = items.store_zone(state, store), state.clock.now()
    out: list[AlternativeOut] = []
    for product in found:
        sold_by = domain.SoldBy(product.sold_by.value if product.sold_by else "unit")
        price = unit_price(
            domain.Product(
                product.product_id, product.size, sold_by, price_info(product.price, zone, now)
            ),
            now,
        )
        out.append(
            AlternativeOut(
                product=items.product_result(product, zone, now),
                unit_price_cents=to_text(price.cents) if price else None,
                unit_price_text=price.text if price else None,
                current=product.product_id == current_id,
            )
        )
    return AlternativesOut(item_id=item_id, alternatives=out)


# ---- a new week -------------------------------------------------------------------------------


@router.post("/plan/new-week")
async def new_week(state: StateDep, session: SessionDep) -> PlanOut:
    async with state.db.write() as tx:
        archived = await service.new_week(tx.session, state.clock.now())
        tx.publish(PLAN_CHANGED)
        archived_id = archived.id if archived else None
    return await listview.plan_view(state, changed=archived_id)


@router.post("/plan/new-week/undo")
async def undo_new_week(body: NewWeekUndo, state: StateDep, session: SessionDep) -> PlanOut:
    async with state.db.write() as tx:
        await service.undo_new_week(tx.session, body.plan_id)
        tx.publish(PLAN_CHANGED)
    return await listview.plan_view(state, changed=body.plan_id)


@router.post("/plan/repeat")
async def repeat_meals(body: RepeatIn, state: StateDep, session: SessionDep) -> PlanOut:
    now = state.clock.now()
    async with state.db.write() as tx:
        trip = await tx.session.get(Trip, body.trip_id)
        if trip is None or trip.plan_id is None:
            raise AppError(404, "trip_not_found", "That trip has no meals to plan again.")
        plan = await service.ensure_plan(tx.session, now)
        member_id = await service.member_for(tx.session, session.device_id)
        added = await service.repeat_meals(tx.session, plan, trip.plan_id, member_id, now)
        if not added:
            raise AppError(409, "no_meals", "Those meals aren't in your library anymore.")
        tx.publish(PLAN_CHANGED)
        tx.publish("dishes.changed")
    return await listview.plan_view(state)


# ---- usual sides ------------------------------------------------------------------------------


@router.get("/dishes/{dish_id}/usual-sides")
async def get_usual_sides(dish_id: str, state: StateDep, session: SessionDep) -> list[UsualSideOut]:
    async with state.db.read() as db:
        return _usual_sides_out(await service.usual_sides(db, dish_id))


@router.put("/dishes/{dish_id}/usual-sides")
async def put_usual_sides(
    dish_id: str, body: UsualSidesIn, state: StateDep, session: SessionDep
) -> list[UsualSideOut]:
    async with state.db.write() as tx:
        await service.set_usual_sides(tx.session, dish_id, body.side_ids)
        await tx.session.flush()
        found = await service.usual_sides(tx.session, dish_id)
        tx.publish("dishes.changed", {"id": dish_id})
        return _usual_sides_out(found)


def _usual_sides_out(found: list[tuple[Dish, DishPairing]]) -> list[UsualSideOut]:
    return [
        UsualSideOut(
            id=dish.id,
            name=dish.name,
            photo_url=photo_url(dish.photo_id, thumb=True),
            pinned=pairing.pinned,
        )
        for dish, pairing in found
    ]
