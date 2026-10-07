"""The plan as the Plan and List screens show it: meals, the merged list, extras and totals.

1. Read the plan in one read session.
2. Fetch Kroger's current data for every product on it, in one batch (nothing from Kroger is
   stored, ADR 0016). If Kroger can't answer, the list still builds from what the household
   confirmed; only prices go missing, and `prices_note` says why.
3. Build the list with the pure domain (PLAN §8.4) and describe each line in plain words.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from fractions import Fraction
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.catalog import service as items
from dinnerbell.catalog.mapping import domain_item, domain_product, price_info, sale_end_day
from dinnerbell.catalog.models import Item
from dinnerbell.domain import listbuild
from dinnerbell.domain import models as domain
from dinnerbell.domain.money import headline_parts
from dinnerbell.domain.rational import to_text
from dinnerbell.domain.sizes import PackageSize, size_label
from dinnerbell.domain.totals import Totals
from dinnerbell.household.models import Member
from dinnerbell.kroger.client import KrogerError
from dinnerbell.kroger.errors import about_time, plain_message
from dinnerbell.kroger.parse import Product
from dinnerbell.meals.models import Dish, DishItem
from dinnerbell.meals.service import photo_url, stored_amount
from dinnerbell.planning.models import (
    Plan,
    PlanExtra,
    PlanItemOverride,
    PlanMeal,
    PlanMealSide,
)
from dinnerbell.planning.schemas import (
    DishRef,
    ExtraOut,
    LineExtraOut,
    LineOut,
    MemberRef,
    PlannedMealOut,
    PlanOut,
    PlanTripOut,
    SaleOut,
    SectionOut,
    TotalsOut,
    UsedByOut,
    UsualOut,
)
from dinnerbell.planning.service import active_plan
from dinnerbell.shopping.models import Trip, TripItem
from dinnerbell.state import AppState
from dinnerbell.stores.models import Store, StoreSection
from dinnerbell.stores.service import active_store

CARD_IMAGES = 3
USUALS = 8
OTHER = ("cat:other", "Other", 9900)
AISLE_ORDER = 1000  # aisles walk in number order between the bakery and the meat counter
SCALES = {Fraction(1, 2): "1/2", Fraction(1): "1", Fraction(2): "2"}


# ---- reading the plan -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Usual:
    item_id: str | None
    text: str | None
    name: str
    product_id: str | None


@dataclass(frozen=True, slots=True)
class SavedList:
    trip: Trip
    items: int
    done: int


@dataclass(frozen=True, slots=True)
class PlanData:
    plan: Plan | None
    meals: list[PlanMeal]  # not removed, in the order the Plan screen shows them
    sides: dict[str, list[str]]  # planned meal id → side ids, in order
    dishes: dict[str, Dish]
    lines: dict[str, list[DishItem]]  # dish id → its item lines, in order
    items: dict[str, Item]
    extras: list[PlanExtra]  # not removed, oldest first
    overrides: dict[str, PlanItemOverride]  # by item id
    members: dict[str, Member]
    store: Store | None
    sections: dict[str, StoreSection]  # by key
    usuals: list[Usual]
    trip: SavedList | None = None  # the plan's saved list, while it's being shopped

    def product_ids(self) -> list[str]:
        ids = {row.product_id for row in self.items.values() if row.product_id}
        ids |= {o.swap_product_id for o in self.overrides.values() if o.swap_product_id}
        return sorted(ids)


async def load(session: AsyncSession) -> PlanData:
    plan = await active_plan(session)
    store = await active_store(session)
    sections: dict[str, StoreSection] = {}
    if store is not None:
        found = await session.scalars(select(StoreSection).where(StoreSection.store_id == store.id))
        sections = {section.key: section for section in found}
    members = {member.id: member for member in await session.scalars(select(Member))}
    if plan is None:
        return PlanData(
            None, [], {}, {}, {}, {}, [], {}, members, store, sections, await _usuals(session, None)
        )

    meals = list(
        await session.scalars(
            select(PlanMeal).where(PlanMeal.plan_id == plan.id, PlanMeal.deleted_at.is_(None))
        )
    )
    meals.sort(key=lambda meal: (meal.day is None, meal.day or date.min, meal.position, meal.id))
    sides: dict[str, list[str]] = {meal.id: [] for meal in meals}
    side_rows = await session.scalars(
        select(PlanMealSide)
        .where(PlanMealSide.plan_meal_id.in_(sides))
        .order_by(PlanMealSide.position)
    )
    for row in side_rows:
        sides[row.plan_meal_id].append(row.side_id)
    dish_ids = {meal.main_id for meal in meals} | {s for ids in sides.values() for s in ids}
    dishes = {
        dish.id: dish for dish in await session.scalars(select(Dish).where(Dish.id.in_(dish_ids)))
    }
    lines: dict[str, list[DishItem]] = {dish_id: [] for dish_id in dishes}
    line_rows = await session.scalars(
        select(DishItem).where(DishItem.dish_id.in_(dishes)).order_by(DishItem.position)
    )
    for line in line_rows:
        lines[line.dish_id].append(line)

    extras = list(
        await session.scalars(
            select(PlanExtra)
            .where(PlanExtra.plan_id == plan.id, PlanExtra.deleted_at.is_(None))
            .order_by(PlanExtra.created_at, PlanExtra.id)
        )
    )
    overrides = {
        o.item_id: o
        for o in await session.scalars(
            select(PlanItemOverride).where(PlanItemOverride.plan_id == plan.id)
        )
    }
    item_ids = {line.item_id for group in lines.values() for line in group}
    item_ids |= {extra.item_id for extra in extras if extra.item_id}
    rows = {row.id: row for row in await session.scalars(select(Item).where(Item.id.in_(item_ids)))}
    return PlanData(
        plan,
        meals,
        sides,
        dishes,
        lines,
        rows,
        extras,
        overrides,
        members,
        store,
        sections,
        await _usuals(session, plan),
        await _saved_list(session, plan),
    )


async def _saved_list(session: AsyncSession, plan: Plan) -> SavedList | None:
    trip = await session.scalar(
        select(Trip)
        .where(Trip.plan_id == plan.id, Trip.status == "active")
        .order_by(Trip.created_at.desc())
        .limit(1)
    )
    if trip is None:
        return None
    states = list(
        await session.scalars(
            select(TripItem.state).where(TripItem.trip_id == trip.id, TripItem.removed_at.is_(None))
        )
    )
    return SavedList(trip, len(states), sum(1 for state in states if state != "todo"))


def trip_out(data: PlanData, built: listbuild.ShoppingList) -> PlanTripOut | None:
    saved = data.trip
    if saved is None:
        return None
    return PlanTripOut(
        id=saved.trip.id,
        item_count=saved.items,
        done_count=saved.done,
        stale=saved.trip.fingerprint != fingerprint(built.lines),
    )


type UsualKey = tuple[str | None, str | None]  # (item id, None) or (None, casefolded text)


def _usual_key(item_id: str | None, text: str | None) -> UsualKey:
    return (item_id, None) if item_id else (None, (text or "").casefold())


async def _usuals(session: AsyncSession, plan: Plan | None) -> list[Usual]:
    """Extras added before (removed ones count), most often first; not ones on the list now."""
    weeks: dict[UsualKey, set[str]] = defaultdict(set)
    latest: dict[UsualKey, tuple[datetime, str | None]] = {}
    history = await session.execute(
        select(PlanExtra.plan_id, PlanExtra.item_id, PlanExtra.text, PlanExtra.created_at)
    )
    for plan_id, item_id, text, created_at in history:
        key = _usual_key(item_id, text)
        weeks[key].add(plan_id)
        if key not in latest or created_at > latest[key][0]:
            latest[key] = (created_at, text)
    if plan is not None:
        active = await session.execute(
            select(PlanExtra.item_id, PlanExtra.text).where(
                PlanExtra.plan_id == plan.id, PlanExtra.deleted_at.is_(None)
            )
        )
        for item_id, text in active:
            weeks.pop(_usual_key(item_id, text), None)
    ids = [item_id for item_id, _ in weeks if item_id]
    rows = {
        row.id: row
        for row in await session.scalars(
            select(Item).where(Item.id.in_(ids), Item.archived_at.is_(None))
        )
    }
    keys = [key for key in weeks if key[0] is None or key[0] in rows]
    keys.sort(key=lambda key: (-len(weeks[key]), -latest[key][0].timestamp(), str(key)))
    usuals: list[Usual] = []
    for key in keys[:USUALS]:
        item_id = key[0]
        if item_id:
            row = rows[item_id]
            usuals.append(Usual(item_id, None, row.name, row.product_id))
        else:
            text = latest[key][1] or ""
            usuals.append(Usual(None, text, text, None))
    return usuals


# ---- Kroger's current data --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Live:
    products: dict[str, Product]  # by product id
    note: str | None  # why prices are missing, when Kroger didn't answer
    zone: ZoneInfo
    now: datetime


async def fetch(state: AppState, data: PlanData) -> Live:
    zone, now = items.store_zone(state, data.store), state.clock.now()
    ids = data.product_ids()
    if data.store is None or not ids:
        return Live({}, None, zone, now)
    try:
        return Live(await state.catalog.products(ids, data.store.location_id), None, zone, now)
    except KrogerError as problem:
        return Live({}, plain_message(problem, state.settings.zone, now), zone, now)


# ---- building the list ------------------------------------------------------------------------


def plan_input(data: PlanData, live: Live) -> domain.PlanInput:
    def dish(dish_id: str) -> domain.Dish:
        row = data.dishes[dish_id]
        return domain.Dish(
            row.id,
            row.name,
            tuple(
                domain.DishLine(line.item_id, stored_amount(line)) for line in data.lines[row.id]
            ),
        )

    meals = tuple(
        domain.Meal(
            meal.id, dish(meal.main_id), tuple(dish(s) for s in data.sides[meal.id]), meal.scale
        )
        for meal in data.meals
    )
    products = {
        row.id: domain_product(live.products.get(row.product_id), row, live.zone, live.now)
        if row.product_id
        else None
        for row in data.items.values()
    }
    overrides = {
        item_id: domain.QuantityOverride(o.qty_delta, domain.PurchaseUnit(o.qty_delta_unit))
        for item_id, o in data.overrides.items()
        if o.qty_delta is not None and o.qty_delta_unit
    }
    swaps = {
        item_id: swap_product(o, live)
        for item_id, o in data.overrides.items()
        if o.swap_product_id and item_id in data.items
    }
    extras = tuple(
        domain.Extra(extra.id, extra.item_id, extra.text, extra.quantity) for extra in data.extras
    )
    return domain.PlanInput(
        meals=meals,
        items={row.id: domain_item(row) for row in data.items.values()},
        products=products,
        have_it=frozenset(i for i, o in data.overrides.items() if o.have_it and i in data.items),
        overrides=overrides,
        swaps=swaps,
        extras=extras,
    )


def swap_product(override: PlanItemOverride, live: Live) -> domain.Product:
    """The swapped product: its size as confirmed when chosen, and Kroger's price right now."""
    assert override.swap_product_id is not None
    product = live.products.get(override.swap_product_id)
    sold_by = product.sold_by.value if product and product.sold_by else override.swap_sold_by
    return domain.Product(
        product_id=override.swap_product_id,
        size_text=override.swap_size_text or (product.size if product else None),
        sold_by=domain.SoldBy(sold_by or "unit"),
        price=price_info(product.price, live.zone, live.now) if product else None,
    )


async def build(state: AppState) -> tuple[PlanData, Live, listbuild.ShoppingList]:
    async with state.db.read() as db:
        data = await load(db)
    live = await fetch(state, data)
    return data, live, listbuild.build_list(plan_input(data, live), live.now)


async def plan_view(state: AppState, changed: str | None = None) -> PlanOut:
    data, live, built = await build(state)
    described = describe(state, data, live, built)
    return PlanOut(
        id=data.plan.id if data.plan else None,
        today=live.now.astimezone(state.settings.zone).date(),
        meals=[meal_out(state, data, meal, live) for meal in data.meals],
        lines=[line for line, _placement in described],
        trip=trip_out(data, built),
        extras=[extra_out(state, data, live, extra, built.lines) for extra in data.extras],
        usuals=[usual_out(state, usual) for usual in data.usuals],
        totals=totals_out(built.totals, state.settings.zone),
        prices_note=live.note,
        changed=changed,
    )


# ---- describing it ----------------------------------------------------------------------------


def member_ref(data: PlanData, member_id: str | None) -> MemberRef | None:
    member = data.members.get(member_id) if member_id else None
    if member is None:
        return None
    return MemberRef(id=member.id, name=member.name, marker_color=member.marker_color)


def dish_ref(state: AppState, data: PlanData, dish_id: str, live: Live) -> DishRef:
    dish = data.dishes[dish_id]
    images: list[str] = []
    for line in data.lines[dish_id]:
        image = item_image(state, data.items[line.item_id], live)
        if image and image not in images:
            images.append(image)
    return DishRef(
        id=dish.id,
        name=dish.name,
        photo_url=photo_url(dish.photo_id, thumb=True),
        item_images=images[:CARD_IMAGES],
        archived=dish.archived_at is not None,
    )


def meal_out(state: AppState, data: PlanData, meal: PlanMeal, live: Live) -> PlannedMealOut:
    return PlannedMealOut(
        id=meal.id,
        main=dish_ref(state, data, meal.main_id, live),
        sides=[dish_ref(state, data, side, live) for side in data.sides[meal.id]],
        day=meal.day,
        occasion=meal.occasion,  # pyright: ignore[reportArgumentType]
        scale=SCALES.get(meal.scale, "1"),  # pyright: ignore[reportArgumentType]
        added_by=member_ref(data, meal.added_by_member_id),
    )


def item_image(state: AppState, row: Item, live: Live, product_id: str | None = None) -> str | None:
    product_id = product_id or row.product_id
    if product_id is None:
        return None
    product = live.products.get(product_id)
    if product is not None:
        return product.image.url() if product.image else None
    return state.catalog.kroger.image_url(product_id)


def product_url(store: Store | None, product: Product | None) -> str | None:
    if product is None or not product.page_uri:
        return None
    domain_name = (store.chain_domain if store else None) or "kroger.com"
    host = domain_name if domain_name.startswith("www.") else f"www.{domain_name}"
    return f"https://{host}{product.page_uri}"


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a line sits on the walk through the store."""

    key: str  # "aisle:12", "cat:produce"
    label: str  # "Aisle 12", "Produce"
    order: int  # the section's place in the walking order
    bay: int = 0  # shelf position within an aisle
    side: str | None = None  # "L" or "R", within an aisle


def place(
    sections: Mapping[str, StoreSection], row: Item | None, product: Product | None
) -> Placement:
    """PLAN §7.3: the household's choice, else the aisle, else the first department the store
    has a section for, else Other. Aisles without a section walk in number order."""

    def known(key: str) -> Placement | None:
        section = sections.get(key)
        return Placement(key, section.label, section.sort_index) if section else None

    if row is not None and row.section_override_key:
        found = known(row.section_override_key)
        if found:
            return found
    if product is not None:
        aisle = product.aisle
        if aisle is not None and aisle.number is not None and aisle.number > 0:
            key = f"aisle:{aisle.number}"
            section = sections.get(key)
            label = section.label if section else f"Aisle {aisle.number}"
            order = section.sort_index if section else AISLE_ORDER + aisle.number
            side = aisle.side if aisle.side in ("L", "R") else None
            return Placement(key, label, order, aisle.bay or 0, side)
        for category in product.categories:
            found = known(f"cat:{_slug(category)}")
            if found:
                return found
    return known(OTHER[0]) or Placement(*OTHER)


def _slug(text: str) -> str:
    words = "".join(c if c.isalnum() else " " for c in text.casefold()).split()
    return "-".join(words)


def _warnings(
    line: listbuild.Line, product: Product | None, row: Item | None, twins: Sequence[str]
) -> list[str]:
    flags = line.flags
    out: list[str] = []
    if twins:  # two items for one product: say so, never merge them (PLAN §8.8)
        out.append(f"Same product as {_join(twins)}")
    out.extend(stock_warnings(product))
    if domain.Flag.HAVE_IT in flags:
        return out
    if domain.Flag.NEEDS_EACH_WEIGHT in flags:
        out.append("Say how much one weighs")
    elif domain.Flag.SIZE_UNKNOWN in flags:
        out.append("Check the size")
    elif domain.Flag.NOT_CONVERTIBLE in flags or domain.Flag.APPROX_SWAP in flags:
        out.append("Check amount")
    if domain.Flag.SHORT in flags:
        out.append("Less than the meals need")
    if line.cost_cents is None and (row is None or row.product_id is None or product is not None):
        out.append("No price")
    return out


def stock_warnings(product: Product | None) -> list[str]:
    if product is None:
        return []
    if product.in_store is False:
        return ["Not sold at your store"]
    if product.stock_level == "TEMPORARILY_OUT_OF_STOCK":
        return ["Out of stock"]
    if product.stock_level == "LOW":
        return ["Low stock"]
    return []


def amount_text(quantity_text: str, unit: str, size_text: str | None, quantity: str) -> str:
    """ "2 boxes, 16 oz each", "1 bag, 8 oz", "1 1/2 lb", "at least 1 package"."""
    if unit != "package" or not size_text or quantity_text.startswith("at least"):
        return quantity_text
    many = quantity not in ("0", "1")
    return f"{quantity_text}, {size_text}{' each' if many else ''}"


def _join(names: Sequence[str]) -> str:
    """ "Milk", "Milk and Whole milk", "A, B and C" (no serial comma, UX §2)."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _twins(lines: Iterable[listbuild.Line]) -> dict[str, list[str]]:
    """For each line, the other lines buying the same product."""
    by_product: dict[str, list[listbuild.Line]] = defaultdict(list)
    for line in lines:
        if line.product_id:
            by_product[line.product_id].append(line)
    return {
        line.key: [other.label for other in group if other.key != line.key]
        for group in by_product.values()
        for line in group
        if len(group) > 1
    }


def line_out(
    state: AppState,
    data: PlanData,
    live: Live,
    line: listbuild.Line,
    names: dict[str, str],
    twins: Sequence[str] = (),
) -> tuple[LineOut, Placement]:
    """The line as the List shows it, and where it sits in the store."""
    row = data.items.get(line.item_id) if line.item_id else None
    product = live.products.get(line.product_id) if line.product_id else None
    override = data.overrides.get(line.item_id) if line.item_id else None
    size = line.size
    placement = place(data.sections, row, product)
    extras = [
        LineExtraOut(
            id=extra.id,
            quantity=to_text(extra.quantity),
            added_by=member_ref(data, extra.added_by_member_id),
        )
        for extra in data.extras
        if (extra.item_id is not None and extra.item_id == line.item_id)
        or line.key == f"extra:{extra.id}"
    ]
    sale = None
    if line.savings_cents > 0 and product is not None and product.price is not None:
        sale = SaleOut(
            savings_cents=line.savings_cents, ends=sale_end_day(product.price, live.zone)
        )
    out = LineOut(
        key=line.key,
        item_id=line.item_id,
        name=line.label,
        image_url=item_image(state, row, live, line.product_id) if row else None,
        product_url=product_url(data.store, product),
        quantity=to_text(line.quantity),
        quantity_text=listbuild.quantity_text(line, size),
        amount_text=amount_text(
            listbuild.quantity_text(line, size),
            line.unit.value,
            size_label(size) if isinstance(size, PackageSize) else None,
            to_text(line.quantity),
        ),
        unit=line.unit.value,  # pyright: ignore[reportArgumentType]
        computed=to_text(line.computed),
        extra=to_text(line.extra),
        at_least=line.at_least,
        needed_text=_needed(line.unconverted),
        size_text=size_label(size) if isinstance(size, PackageSize) else None,
        cost_cents=line.cost_cents,
        regular_cents=line.regular_cents,
        sale=sale,
        estimated_weight=domain.Flag.EST_EACH_WEIGHT in line.flags,
        used_by=[
            UsedByOut(
                meal_id=use.meal_id,
                name=names.get(use.meal_id, ""),
                dish_names=list(use.dish_names),
            )
            for use in line.used_by
        ],
        extras=extras,
        have_it=override.have_it if override else None,
        staple=bool(row and row.is_staple),
        swapped=domain.Flag.SWAPPED in line.flags,
        warnings=_warnings(line, product, row, twins),
        flags=sorted(flag.value for flag in line.flags),
        section=SectionOut(key=placement.key, label=placement.label, order=placement.order),
    )
    return out, placement


def _needed(amounts: Sequence[domain.Amount]) -> str | None:
    if not amounts:
        return None
    parts = [items.amount_text(amount, None) for amount in amounts]
    return f"{' and '.join(parts)} needed"


def in_walking_order(
    described: Iterable[tuple[LineOut, Placement]],
) -> list[tuple[LineOut, Placement]]:
    """Sections in the store's order, then shelf position, then name. An aisle whose lines are
    all on one side says so: "Aisle 12, left side"."""
    ordered = sorted(
        described,
        key=lambda pair: (pair[1].order, pair[1].bay, pair[0].name.casefold(), pair[0].key),
    )
    sides: dict[str, set[str | None]] = defaultdict(set)
    for _line, placement in ordered:
        sides[placement.key].add(placement.side)
    out: list[tuple[LineOut, Placement]] = []
    for line, placement in ordered:
        side = next(iter(sides[placement.key])) if len(sides[placement.key]) == 1 else None
        if side is not None and placement.key.startswith("aisle:"):
            label = f"{placement.label}, {'left' if side == 'L' else 'right'} side"
            line = line.model_copy(
                update={"section": line.section.model_copy(update={"label": label})}
            )
        out.append((line, placement))
    return out


def describe(
    state: AppState, data: PlanData, live: Live, built: listbuild.ShoppingList
) -> list[tuple[LineOut, Placement]]:
    """Every line as the List shows it, in walking order, with where it sits in the store."""
    names = {meal.id: data.dishes[meal.main_id].name for meal in data.meals}
    twins = _twins(built.lines)
    return in_walking_order(
        line_out(state, data, live, line, names, twins.get(line.key, ())) for line in built.lines
    )


def shoppable(line: listbuild.Line) -> bool:
    """Lines a saved list keeps: not ones the household has, nor ones set to zero."""
    return not line.have_it and line.quantity > 0


def fingerprint(lines: Iterable[listbuild.Line]) -> str:
    """What the list asks to buy, so a saved list can tell when the plan's list has changed."""
    parts = sorted(
        f"{line.key}|{to_text(line.quantity)}|{line.unit.value}|{line.product_id or ''}"
        for line in lines
        if shoppable(line)
    )
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def extra_out(
    state: AppState, data: PlanData, live: Live, extra: PlanExtra, lines: Iterable[listbuild.Line]
) -> ExtraOut:
    key = extra.item_id or f"extra:{extra.id}"
    line = next((line for line in lines if line.key == key), None)
    row = data.items.get(extra.item_id) if extra.item_id else None
    unit = line.unit if line else domain.PurchaseUnit.PACKAGE
    return ExtraOut(
        id=extra.id,
        item_id=extra.item_id,
        text=extra.text,
        name=row.name if row else (extra.text or ""),
        image_url=item_image(state, row, live) if row else None,
        quantity=to_text(extra.quantity),
        quantity_text=listbuild.quantity_words(unit, extra.quantity, line.size if line else None),
        note=extra.note,
        added_by=member_ref(data, extra.added_by_member_id),
        line_key=key,
    )


def usual_out(state: AppState, usual: Usual) -> UsualOut:
    image = state.catalog.kroger.image_url(usual.product_id) if usual.product_id else None
    return UsualOut(item_id=usual.item_id, text=usual.text, name=usual.name, image_url=image)


def totals_out(totals: Totals, zone: ZoneInfo) -> TotalsOut:
    """The numbers, and the words the footer shows (the domain's headline, one per line)."""
    as_of = totals.prices_as_of
    words = headline_parts(totals, about_time(as_of, zone, as_of) if as_of else "")
    return TotalsOut(
        total_cents=totals.total,
        savings_cents=totals.savings,
        regular_total_cents=totals.regular_total,
        not_priced=totals.not_priced,
        needs_check=totals.needs_check,
        have_it=totals.have_it,
        prices_as_of=as_of,
        total_text=words.total,
        savings_text=words.savings,
        prices_as_of_text=words.prices_as_of,
        not_priced_text=words.not_priced,
    )
