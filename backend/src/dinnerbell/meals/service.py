"""Mains and Sides: create, edit, duplicate, archive, and their estimated cost.

* Saving checks every line against what the household confirmed for its item (size, unit or
  weight); no Kroger call is needed, so saving works even when Kroger doesn't answer.
* Reading re-checks each line against Kroger's current data: if a size fix makes an amount
  impossible, the line says "check amount" instead of failing (PLAN §8.7).
* A dish's cost is the sum of its lines' shares at today's prices (UX §4.6 "about $14").
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.catalog import service as items
from dinnerbell.catalog.mapping import (
    confirmed_product,
    domain_item,
    domain_product,
    price_info,
    sale_end_day,
)
from dinnerbell.catalog.models import Item
from dinnerbell.core.errors import AppError
from dinnerbell.domain import amounts
from dinnerbell.domain import models as domain
from dinnerbell.domain.money import about_dollars, promo_valid
from dinnerbell.domain.units import Unit
from dinnerbell.kroger.client import KrogerError
from dinnerbell.kroger.parse import Product
from dinnerbell.meals.models import Dish, DishItem, Photo
from dinnerbell.meals.schemas import CostOut, DishCard, DishLineOut, DishOut, LineIn
from dinnerbell.planning.occasions import default_occasions
from dinnerbell.state import AppState
from dinnerbell.stores.service import active_store

CARD_IMAGES = 3
ORPHAN_PHOTO_AGE = timedelta(days=7)


# ---- prices for one request -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Pricing:
    """Kroger's data for the items on screen, fetched once, before any write transaction."""

    products: dict[str, Product]
    zone: ZoneInfo
    now: datetime

    def product(self, row: Item) -> Product | None:
        return self.products.get(row.product_id) if row.product_id else None

    def target(self, row: Item) -> domain.Product | None:
        return domain_product(self.product(row), row, self.zone, self.now)

    def sale(self, row: Item) -> tuple[bool, date | None] | None:
        """(True, its last day) when the item's product is on sale today; else None."""
        product = self.product(row)
        if product is None or product.price is None:
            return None
        info = price_info(product.price, self.zone, self.now)
        if info is None or not promo_valid(info, self.now):
            return None
        return True, sale_end_day(product.price, self.zone)


async def pricing_for(state: AppState, rows: Iterable[Item]) -> Pricing:
    async with state.db.read() as db:
        store = await active_store(db)
    zone, now = items.store_zone(state, store), state.clock.now()
    ids = sorted({row.product_id for row in rows if row.product_id})
    products: dict[str, Product] = {}
    if store is not None and ids:
        try:
            products = await state.catalog.products(ids, store.location_id)
        except KrogerError:
            products = {}  # prices go missing; everything else still works
    return Pricing(products, zone, now)


# ---- reading --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Loaded:
    dishes: list[Dish]
    lines: dict[str, list[DishItem]]
    items: dict[str, Item]


async def load(session: AsyncSession, dishes: Sequence[Dish]) -> Loaded:
    ids = [dish.id for dish in dishes]
    lines: dict[str, list[DishItem]] = {dish_id: [] for dish_id in ids}
    rows = await session.scalars(
        select(DishItem).where(DishItem.dish_id.in_(ids)).order_by(DishItem.position)
    )
    for line in rows:
        lines[line.dish_id].append(line)
    item_ids = {line.item_id for group in lines.values() for line in group}
    found = await session.scalars(select(Item).where(Item.id.in_(item_ids)))
    return Loaded(list(dishes), lines, {row.id: row for row in found})


def line_out(state: AppState, line: DishItem, row: Item, pricing: Pricing) -> DishLineOut:
    item = domain_item(row)
    target = pricing.target(row)
    amount = stored_amount(line)
    size = domain.effective_size(item, target)
    try:
        amounts.validate_amount(amount, item, target)
    except domain.InvalidAmount as problem:
        check: str | None = problem.message
        share, cost = None, None
    else:
        check = None
        share = amounts.share_text(amount, item, target)
        cost = amounts.share_cost(amount, item, target, pricing.now)
    return DishLineOut(
        id=line.id,
        item=items.item_out(state, row, pricing.product(row)),
        amount=items.amount_out(amount, size),
        share_text=share,
        cost_cents=cost,
        check_amount=check,
    )


def stored_amount(line: DishItem) -> domain.Amount:
    unit = Unit(line.unit) if line.unit else None
    return domain.Amount(domain.AmountKind(line.amount_kind), line.amount, unit)


def cost_of(lines: Sequence[DishLineOut]) -> CostOut:
    priced = [line.cost_cents for line in lines if line.cost_cents is not None]
    cents = sum(priced) if priced else None
    return CostOut(
        about_dollars=about_dollars(cents) if cents is not None else None,
        cents=cents,
        unpriced=len(lines) - len(priced),
    )


def photo_url(photo_id: str | None, *, thumb: bool) -> str | None:
    if photo_id is None:
        return None
    return f"/api/photos/{photo_id}/thumb" if thumb else f"/api/photos/{photo_id}"


async def get_dish(session: AsyncSession, dish_id: str) -> Dish:
    dish = await session.get(Dish, dish_id)
    if dish is None:
        raise AppError(404, "dish_not_found", "That meal couldn't be found.")
    return dish


async def dish_out(state: AppState, dish_id: str) -> DishOut:
    async with state.db.read() as db:
        loaded = await load(db, [await get_dish(db, dish_id)])
        defaults = await default_occasions(db, [dish_id])
    pricing = await pricing_for(state, loaded.items.values())
    dish = loaded.dishes[0]
    lines = [
        line_out(state, line, loaded.items[line.item_id], pricing) for line in loaded.lines[dish.id]
    ]
    return DishOut(
        id=dish.id,
        name=dish.name,
        role="side" if dish.role == "side" else "main",
        occasions=dish.occasions,  # pyright: ignore[reportArgumentType]
        default_occasion=defaults[dish.id],  # pyright: ignore[reportArgumentType]
        servings=dish.servings,
        notes=dish.notes,
        recipe_url=dish.recipe_url,
        favorite=dish.favorite,
        photo_id=dish.photo_id,
        photo_url=photo_url(dish.photo_id, thumb=False),
        archived=dish.archived_at is not None,
        lines=lines,
        cost=cost_of(lines),
    )


async def cards(
    state: AppState,
    *,
    role: str | None,
    query: str | None,
    occasion: str | None,
    favorite: bool | None,
    archived: bool,
) -> list[DishCard]:
    async with state.db.read() as db:
        statement = select(Dish).where(
            Dish.archived_at.is_not(None) if archived else Dish.archived_at.is_(None)
        )
        if role:
            statement = statement.where(Dish.role == role)
        if favorite is not None:
            statement = statement.where(Dish.favorite.is_(favorite))
        found = list(await db.scalars(statement))
        if query:
            needle = query.casefold().strip()
            found = [dish for dish in found if needle in dish.name.casefold()]
        if occasion:
            found = [dish for dish in found if occasion in dish.occasions]
        found.sort(key=lambda dish: (not dish.favorite, dish.name.casefold(), dish.id))
        loaded = await load(db, found)
        defaults = await default_occasions(db, [dish.id for dish in found])
    pricing = await pricing_for(state, loaded.items.values())
    out: list[DishCard] = []
    for dish in loaded.dishes:
        rows = [loaded.items[line.item_id] for line in loaded.lines[dish.id]]
        lines = [
            line_out(state, line, row, pricing)
            for line, row in zip(loaded.lines[dish.id], rows, strict=True)
        ]
        images = [line.item.image_url for line in lines if line.item.image_url]
        sales = [sale for row in rows if (sale := pricing.sale(row)) is not None]
        out.append(
            DishCard(
                id=dish.id,
                name=dish.name,
                role="side" if dish.role == "side" else "main",
                occasions=dish.occasions,  # pyright: ignore[reportArgumentType]
                default_occasion=defaults[dish.id],  # pyright: ignore[reportArgumentType]
                favorite=dish.favorite,
                photo_url=photo_url(dish.photo_id, thumb=True),
                item_images=list(dict.fromkeys(images))[:CARD_IMAGES],
                cost=cost_of(lines),
                on_sale=bool(sales),
                sale_ends=min((end for _on, end in sales if end is not None), default=None),
                archived=dish.archived_at is not None,
            )
        )
    return out


# ---- writing --------------------------------------------------------------------------------


async def checked_lines(
    session: AsyncSession, given: Sequence[LineIn]
) -> list[tuple[Item, domain.Amount]]:
    """Every line's item exists and its amount fits what the household confirmed for it."""
    ids = {line.item_id for line in given}
    rows = {row.id: row for row in await session.scalars(select(Item).where(Item.id.in_(ids)))}
    checked: list[tuple[Item, domain.Amount]] = []
    for line in given:
        row = rows.get(line.item_id)
        if row is None or row.archived_at is not None:
            raise AppError(404, "item_not_found", "One of the items is gone. Add it again.")
        try:
            amount = items.to_amount(line.amount)
            amounts.validate_amount(amount, domain_item(row), confirmed_product(row))
        except domain.InvalidAmount as problem:
            raise AppError(422, "amount_invalid", f"{row.name}: {problem.message}") from None
        checked.append((row, amount))
    return checked


def write_lines(
    session: AsyncSession, dish: Dish, lines: Sequence[tuple[Item, domain.Amount]]
) -> None:
    for position, (row, amount) in enumerate(lines):
        session.add(
            DishItem(
                dish_id=dish.id,
                item_id=row.id,
                amount_kind=amount.kind.value,
                amount=amount.value,
                unit=amount.unit.value if amount.unit else None,
                position=position,
            )
        )


async def check_photo(session: AsyncSession, photo_id: str | None) -> None:
    if photo_id is not None and await session.get(Photo, photo_id) is None:
        raise AppError(404, "photo_not_found", "That photo is gone. Add it again.")


async def replace_lines(
    session: AsyncSession, dish: Dish, lines: Sequence[tuple[Item, domain.Amount]]
) -> None:
    await session.execute(delete(DishItem).where(DishItem.dish_id == dish.id))
    await session.flush()
    write_lines(session, dish, lines)


async def duplicate(session: AsyncSession, dish: Dish) -> Dish:
    copy = Dish(
        name=f"{dish.name} (copy)"[:80],
        role=dish.role,
        occasions=list(dish.occasions),
        servings=dish.servings,
        photo_id=dish.photo_id,
        notes=dish.notes,
        recipe_url=dish.recipe_url,
        favorite=False,
    )
    session.add(copy)
    await session.flush()
    originals = await session.scalars(
        select(DishItem).where(DishItem.dish_id == dish.id).order_by(DishItem.position)
    )
    for line in originals:
        session.add(
            DishItem(
                dish_id=copy.id,
                item_id=line.item_id,
                amount_kind=line.amount_kind,
                amount=line.amount,
                unit=line.unit,
                position=line.position,
            )
        )
    return copy


async def purge_orphan_photos(session: AsyncSession, now: datetime) -> int:
    """Photos no meal uses, a week after they were taken (drafts keep theirs that long)."""
    unused = ~exists().where(Dish.photo_id == Photo.id)
    stale = select(Photo.id).where(unused, Photo.created_at < now - ORPHAN_PHOTO_AGE)
    ids = list(await session.scalars(stale))
    if ids:
        await session.execute(delete(Photo).where(Photo.id.in_(ids)))
    return len(ids)
