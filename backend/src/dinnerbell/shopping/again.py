"""Shop this again (UX §4.15): a new saved list with a past trip's items and amounts, priced at
today's prices. Each item buys its current product (so "Always use this" carries over);
plain-text lines come along as they were. The new list stands on its own, outside any plan.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.catalog.mapping import domain_product
from dinnerbell.catalog.models import Item
from dinnerbell.domain.listbuild import price_quantity
from dinnerbell.domain.models import PurchaseUnit
from dinnerbell.kroger.parse import Product
from dinnerbell.planning.listview import Placement, place, product_url, stock_warnings
from dinnerbell.shopping.models import Trip, TripItem
from dinnerbell.shopping.service import bump, ensure_aisles, ms
from dinnerbell.stores.models import Store, StoreSection


def lines_again(
    old: Sequence[TripItem],
    rows: Mapping[str, Item],
    products: Mapping[str, Product],
    store: Store | None,
    sections: Mapping[str, StoreSection],
    zone: ZoneInfo,
    now: datetime,
    image_for: Callable[[str], str],
) -> list[dict[str, Any]]:
    """The new list's lines, as TripItem values, in the store's walking order."""
    out: list[dict[str, Any]] = []
    for item in old:
        row = rows.get(item.item_id) if item.item_id else None
        product_id = row.product_id if row else None
        live = products.get(product_id) if product_id else None
        target = domain_product(live, row, zone, now) if row else None
        price = price_quantity(
            PurchaseUnit(item.unit),
            item.quantity,
            target,
            row.each_weight_lb if row else None,
            now,
        )
        spot = place(sections, row, live)
        image = None
        if product_id:
            image = (live.image.url() if live.image else None) if live else image_for(product_id)
        out.append(
            {
                "line_key": item.line_key,
                "item_id": item.item_id,
                "name": row.name if row else item.name,
                "product_id": product_id,
                "upc": row.upc if row and product_id else None,
                "image_url": image,
                "product_url": product_url(store, live),
                "size_text": item.size_text,
                "qty_text": item.qty_text,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_cents": price.unit_cents if price else None,
                "line_cents": price.cost_cents if price else None,
                "regular_cents": price.regular_cents if price else None,
                "on_sale": bool(price and price.on_sale),
                "sale_ends": None,
                "section_key": spot.key,
                "section_label": spot.label,
                "section_order": spot.order,
                "aisle_side": spot.side,
                "bay": spot.bay,
                "used_by": list(item.used_by),
                "warnings": stock_warnings(live),
            }
        )
    out.sort(key=lambda v: (v["section_order"], v["bay"], v["name"].casefold(), v["line_key"]))
    for position, values in enumerate(out):
        values["position"] = position
    return out


async def create(
    session: AsyncSession,
    lines: Sequence[dict[str, Any]],
    store: Store | None,
    member_id: str | None,
    now: datetime,
) -> Trip:
    priced = [v for v in lines if v["line_cents"] is not None]
    trip = Trip(
        plan_id=None,
        store_id=store.id if store else None,
        status="active",
        status_ts=ms(now),
        status_by_member_id=member_id,
        created_by_member_id=member_id,
        created_at=now,
        version=0,
        estimate_cents=sum(v["line_cents"] for v in priced),
        savings_cents=sum((v["regular_cents"] or 0) - v["line_cents"] for v in priced),
        not_priced=len(lines) - len(priced),
        prices_as_of=now if priced else None,
    )
    session.add(trip)
    await session.flush()
    places = [
        Placement(v["section_key"], v["section_label"], v["section_order"], v["bay"], None)
        for v in lines
    ]
    orders = await ensure_aisles(session, store, places)
    for values in lines:
        item = TripItem(trip_id=trip.id, **values)
        if values["section_key"] in orders:
            item.section_order = orders[values["section_key"]]
        session.add(item)
        bump(trip, item)
    bump(trip)
    await session.flush()
    return trip
