"""Kroger products and item rows → the pure domain's types (docs/PLAN.md §8).

Kroger's promo dates arrive as dates or instants. A date-only start means the start of that
local day, and a date-only end lasts through the end of that local day (PLAN §8.8), both in
the store's time zone.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dinnerbell.catalog.models import Item
from dinnerbell.domain import models as domain
from dinnerbell.domain.money import PriceInfo
from dinnerbell.domain.sizes import PackageSize, parse_size
from dinnerbell.kroger import parse as kroger


def domain_item(row: Item) -> domain.Item:
    size = parse_size(row.size_text) if row.size_text else None
    return domain.Item(
        id=row.id,
        name=row.name,
        size_override=size if isinstance(size, PackageSize) else None,
        each_weight=row.each_weight_lb,
    )


def domain_product(
    product: kroger.Product | None, row: Item, zone: ZoneInfo, now: datetime
) -> domain.Product | None:
    """Kroger's live data when we have it; otherwise what the household confirmed when linking."""
    if product is not None:
        return domain.Product(
            product_id=product.product_id,
            size_text=product.size,
            sold_by=_sold_by(product.sold_by.value if product.sold_by else row.sold_by),
            price=price_info(product.price, zone, now),
        )
    return confirmed_product(row)


def confirmed_product(row: Item) -> domain.Product | None:
    """What the household confirmed when linking: enough to check an amount, never a price."""
    if row.product_id is None:
        return None
    return domain.Product(
        product_id=row.product_id, size_text=row.size_text, sold_by=_sold_by(row.sold_by)
    )


def price_info(price: kroger.Price | None, zone: ZoneInfo, now: datetime) -> PriceInfo | None:
    if price is None:
        return None
    return PriceInfo(
        regular=price.regular,
        promo=price.promo,
        promo_from=_starts(price.effective, zone),
        promo_until=_ends(price.expires, zone),
        each_estimate=price.regular_each_estimate,
        fetched_at=now,
    )


def sale_end_day(price: kroger.Price, zone: ZoneInfo) -> date | None:
    """The last day a sale runs, as the household would say it ("Sale ends Oct 14")."""
    until = _ends(price.expires, zone)
    return None if until is None else (until - timedelta(microseconds=1)).astimezone(zone).date()


def _sold_by(value: str | None) -> domain.SoldBy:
    return domain.SoldBy.WEIGHT if (value or "").upper() == "WEIGHT" else domain.SoldBy.UNIT


def _starts(value: datetime | date | None, zone: ZoneInfo) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.combine(value, time(0), tzinfo=zone)


def _ends(value: datetime | date | None, zone: ZoneInfo) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.combine(value + timedelta(days=1), time(0), tzinfo=zone)
