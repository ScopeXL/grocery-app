"""Items, product search and the amount picker (docs/PLAN.md §7.4, §8.7; UX §4.9 and §4.10).

Kroger calls happen before any write transaction opens (the catalog writes its own cache).
When Kroger can't be reached, items still work from what the household confirmed when
linking: the size and how the product is sold. Only prices go missing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from fractions import Fraction
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.catalog.mapping import (
    domain_item,
    domain_product,
    price_info,
    sale_end_day,
)
from dinnerbell.catalog.models import Item
from dinnerbell.catalog.schemas import (
    AmountIn,
    AmountOut,
    EachWeightOut,
    ItemOut,
    KindOptionOut,
    PickerOut,
    PreviewOut,
    PriceOut,
    ProductResult,
)
from dinnerbell.core.errors import AppError
from dinnerbell.domain import amounts
from dinnerbell.domain import models as domain
from dinnerbell.domain.money import promo_valid
from dinnerbell.domain.rational import q, to_mixed, to_text
from dinnerbell.domain.sizes import PackageSize, Unparseable, format_size, parse_size
from dinnerbell.domain.units import Unit
from dinnerbell.kroger.client import KrogerError
from dinnerbell.kroger.parse import Product, SoldBy
from dinnerbell.state import AppState
from dinnerbell.stores.models import Store
from dinnerbell.stores.service import active_store

SEARCH_LIMIT = 20
MAX_TERM_WORDS = 8
MAX_EACH_WEIGHT = Fraction(20)  # pounds; anything heavier is a typo
UNIT_TEXT = {Unit.FL_OZ: "fl oz"}


# ---- the store ----------------------------------------------------------------------------


async def require_store(state: AppState) -> Store:
    async with state.db.read() as db:
        store = await active_store(db)
    if store is None:
        raise AppError(409, "store_required", "Choose your store first.")
    return store


def store_zone(state: AppState, store: Store | None) -> ZoneInfo:
    if store is not None and store.timezone:
        try:
            return ZoneInfo(store.timezone)
        except KeyError, ValueError:
            pass
    return state.settings.zone


# ---- product search -------------------------------------------------------------------------


async def search_products(state: AppState, term: str) -> list[ProductResult]:
    words = term.split()
    if len("".join(words)) < 3:
        raise AppError(422, "term_too_short", "Type at least 3 letters.")
    if len(words) > MAX_TERM_WORDS:
        raise AppError(422, "term_too_long", "Use 8 words or fewer.")
    store = await require_store(state)
    found = await state.catalog.search(" ".join(words), store.location_id, limit=SEARCH_LIMIT)
    zone, now = store_zone(state, store), state.clock.now()
    return [product_result(product, zone, now) for product in found]


def product_result(product: Product, zone: ZoneInfo, now: datetime) -> ProductResult:
    image = product.image.url() if product.image else None
    return ProductResult(
        product_id=product.product_id,
        description=product.description,
        brand=product.brand,
        size=product.size,
        image_url=image,
        price=price_out(product, zone, now),
        availability=_availability(product),
        sold_by="weight" if product.sold_by is SoldBy.WEIGHT else "unit",
    )


def price_out(product: Product, zone: ZoneInfo, now: datetime) -> PriceOut | None:
    price = product.price
    if price is None or price.regular is None:
        return None
    info = price_info(price, zone, now)
    on_sale = info is not None and promo_valid(info, now)
    return PriceOut(
        regular_cents=price.regular,
        sale_cents=price.promo if on_sale else None,
        sale_ends=sale_end_day(price, zone) if on_sale else None,
        per_pound=product.sold_by is SoldBy.WEIGHT,
    )


def _availability(product: Product) -> Literal["available", "low", "out", "not_sold"]:
    if product.in_store is False:
        return "not_sold"
    if product.stock_level == "TEMPORARILY_OUT_OF_STOCK":
        return "out"
    if product.stock_level == "LOW":
        return "low"
    return "available"


async def product_for(state: AppState, row: Item, store: Store | None) -> Product | None:
    """Kroger's current data for a linked item, or None when it can't be had right now."""
    if row.product_id is None or store is None:
        return None
    try:
        return await state.catalog.product(row.product_id, store.location_id)
    except KrogerError:
        return None


# ---- items ----------------------------------------------------------------------------------


async def list_items(session: AsyncSession, query: str | None) -> Sequence[Item]:
    statement = select(Item).where(Item.archived_at.is_(None)).order_by(Item.name)
    rows = list(await session.scalars(statement))
    if query:
        needle = query.casefold().strip()
        rows = [row for row in rows if needle in row.name.casefold()]
    return rows


async def get_item(session: AsyncSession, item_id: str) -> Item:
    row = await session.get(Item, item_id)
    if row is None:
        raise AppError(404, "item_not_found", "That item couldn't be found.")
    return row


async def linked_product(state: AppState, product_id: str) -> Product:
    """Fetch the product being linked, before the write transaction opens."""
    store = await require_store(state)
    product = await state.catalog.product(product_id, store.location_id)
    if product is None:
        raise AppError(
            404, "product_not_found", "That product isn't at your store anymore. Search again."
        )
    return product


def link(row: Item, product: Product | None) -> None:
    """Record what the household confirms by choosing this product (ADR 0016)."""
    if product is None:
        row.product_id = row.upc = row.sold_by = row.size_text = None
        row.size_source = "parsed"
        return
    row.product_id = product.product_id
    row.upc = product.upc
    row.sold_by = (product.sold_by or SoldBy.UNIT).value
    size = parse_size(product.size)
    row.size_text = format_size(size) if isinstance(size, PackageSize) else None
    row.size_source = "parsed"


def fix_size(row: Item, text: str) -> None:
    size = parse_size(text)
    if isinstance(size, Unparseable):
        raise AppError(
            422,
            "size_unreadable",
            'That size couldn\'t be read. Write it like "16 oz", "2 lb", "12 ct" or "64 fl oz".',
        )
    row.size_text = format_size(size)
    row.size_source = "household"


def set_each_weight(row: Item, text: str | None) -> None:
    if text is None:
        row.each_weight_lb = None
        return
    weight = parse_number(text)
    if weight is None or not 0 < weight <= MAX_EACH_WEIGHT:
        raise AppError(422, "each_weight_invalid", "Choose a weight between 1 oz and 20 lb.")
    row.each_weight_lb = weight


def item_out(state: AppState, row: Item, product: Product | None = None) -> ItemOut:
    """`product`, when already fetched, gives the real photo (or none); else it's derived."""
    if product is not None:
        image = product.image.url() if product.image else None
    elif row.product_id:
        image = state.catalog.kroger.image_url(row.product_id)
    else:
        image = None
    return ItemOut(
        id=row.id,
        name=row.name,
        product_id=row.product_id,
        image_url=image,
        size_text=row.size_text,
        size_source="household" if row.size_source == "household" else "parsed",
        sold_by=None if row.sold_by is None else ("weight" if row.sold_by == "WEIGHT" else "unit"),
        each_weight_lb=to_text(row.each_weight_lb) if row.each_weight_lb is not None else None,
        is_staple=row.is_staple,
        archived=row.archived_at is not None,
    )


# ---- amounts --------------------------------------------------------------------------------


def parse_number(text: str) -> Fraction | None:
    try:
        return q(text)
    except TypeError, ValueError, ZeroDivisionError:
        return None


def to_amount(given: AmountIn) -> domain.Amount:
    """API text → a domain Amount, or InvalidAmount with a plain-English message."""
    value = parse_number(given.value)
    if value is None:
        raise domain.InvalidAmount("That amount isn't a number. Try 1/2 or 0.5.")
    try:
        unit = Unit(given.unit) if given.unit else None
    except ValueError:
        raise domain.InvalidAmount("That unit isn't one Dinner Bell knows.") from None
    return domain.Amount(domain.AmountKind(given.kind), value, unit)


def amount_out(amount: domain.Amount, size: PackageSize | Unparseable | None) -> AmountOut:
    return AmountOut(
        kind=amount.kind.value,
        value=to_text(amount.value),
        unit=amount.unit.value if amount.unit else None,
        text=amount_text(amount, size),
    )


def amount_text(amount: domain.Amount, size: PackageSize | Unparseable | None) -> str:
    """How a dish line shows its amount: "1/2 bag", "2 packages", "6 oz", "3"."""
    number = to_mixed(amount.value)
    if amount.kind is domain.AmountKind.MEASURE and amount.unit is not None:
        return f"{number} {UNIT_TEXT.get(amount.unit, amount.unit.value)}"
    if amount.kind is domain.AmountKind.COUNT:
        return number
    container = size.container if isinstance(size, PackageSize) else None
    if container is not None:
        return f"{number} {container.plural if amount.value > 1 else container.value}"
    return f"{number} {'packages' if amount.value > 1 else 'package'}"


async def picker(state: AppState, item_id: str) -> PickerOut:
    async with state.db.read() as db:
        row = await get_item(db, item_id)
        store = await active_store(db)
    product = await product_for(state, row, store)
    zone, now = store_zone(state, store), state.clock.now()
    item = domain_item(row)
    target = domain_product(product, row, zone, now)
    options = amounts.amount_options(item, target)
    size = domain.effective_size(item, target)
    question = options.each_weight
    return PickerOut(
        item=item_out(state, row, product),
        product=product_result(product, zone, now) if product else None,
        kinds=[
            KindOptionOut(
                kind=option.kind.value,
                units=[unit.value for unit in option.units],
                presets=[amount_out(preset, size) for preset in option.presets],
                step=to_text(option.step) if option.step is not None else None,
            )
            for option in options.kinds
        ],
        each_weight=EachWeightOut(
            presets=[to_text(p) for p in question.presets],
            prefill=to_text(question.prefill) if question.prefill is not None else None,
        )
        if question
        else None,
        fix_size=options.fix_size,
    )


async def preview(state: AppState, item_id: str, given: AmountIn) -> PreviewOut:
    async with state.db.read() as db:
        row = await get_item(db, item_id)
        store = await active_store(db)
    product = await product_for(state, row, store)
    now = state.clock.now()
    item = domain_item(row)
    target = domain_product(product, row, store_zone(state, store), now)
    try:
        amount = to_amount(given)
        amounts.validate_amount(amount, item, target)
    except domain.InvalidAmount as rejected:
        return PreviewOut(
            valid=False, message=rejected.message, amount=None, share_text=None, cost_cents=None
        )
    return PreviewOut(
        valid=True,
        message=None,
        amount=amount_out(amount, domain.effective_size(item, target)),
        share_text=amounts.share_text(amount, item, target),
        cost_cents=amounts.share_cost(amount, item, target, now),
    )
