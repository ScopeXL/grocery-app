"""Kroger API responses → typed, read-only objects (docs/PLAN.md §7.1).

Parsing forgives Kroger's quirks: `soldBy` casing, `inStore`/`instore` keys, a `promo` of 0,
placeholder aisles ("PRODUCE", number 0), `Open24`/`open24`. Prices become integer cents here,
from the Decimals that `json.loads(..., parse_float=Decimal)` produces; a float is refused, so
floats never touch money. Product data is shown exactly as Kroger returns it (never rewritten).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from fractions import Fraction
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FUEL_CHAIN = "SHELL COMPANY"
IMAGE_SIZES = ("medium", "large", "small", "xlarge", "thumbnail")  # display preference


class SoldBy(StrEnum):
    UNIT = "UNIT"
    WEIGHT = "WEIGHT"


@dataclass(frozen=True, slots=True)
class Aisle:
    number: int | None  # None for placeholders such as "PRODUCE" / 0
    side: str | None  # "L" or "R"
    description: str | None
    bay: int | None


@dataclass(frozen=True, slots=True)
class Price:
    regular: int | None  # cents
    promo: int | None  # cents; None when missing or 0 (Kroger's "no promo")
    regular_each_estimate: Fraction | None  # cents; `regularPerUnitEstimate`, often unreliable
    effective: datetime | date | None  # a date means "from the start of that local day"
    expires: datetime | date | None  # a date means "through the end of that local day"


@dataclass(frozen=True, slots=True)
class ProductImage:
    sizes: tuple[tuple[str, str], ...]  # (size, url) pairs as Kroger lists them

    def url(self, *preferred: str) -> str | None:
        by_size = dict(self.sizes)
        for size in preferred or IMAGE_SIZES:
            if size in by_size:
                return by_size[size]
        return self.sizes[0][1] if self.sizes else None


@dataclass(frozen=True, slots=True)
class Product:
    product_id: str
    upc: str | None
    description: str
    brand: str | None
    categories: tuple[str, ...]
    page_uri: str | None
    image: ProductImage | None
    size: str | None  # Kroger's size text, exactly as returned ("16 fl oz (473 mL)")
    sold_by: SoldBy | None
    price: Price | None
    stock_level: str | None  # HIGH, LOW, TEMPORARILY_OUT_OF_STOCK
    in_store: bool | None
    aisles: tuple[Aisle, ...]

    @property
    def aisle(self) -> Aisle | None:
        """The first real aisle (placeholders don't count)."""
        return next((aisle for aisle in self.aisles if aisle.number is not None), None)


@dataclass(frozen=True, slots=True)
class Location:
    location_id: str
    chain: str
    name: str
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    timezone: str | None
    departments: tuple[str, ...]

    @property
    def is_fuel_center(self) -> bool:
        return self.chain.strip().upper() == FUEL_CHAIN


@dataclass(frozen=True, slots=True)
class Chain:
    name: str
    domain: str | None
    division_numbers: tuple[str, ...]


# ---- entry points ---------------------------------------------------------------------------


def parse_products(body: Any) -> tuple[Product, ...]:
    """`{"data": [...]}` from a search or batch, or `{"data": {...}}` from a single product."""
    data = _obj(body).get("data")
    raws = _list(data) if isinstance(data, list) else [data]
    return tuple(product for raw in raws if (product := parse_product(raw)) is not None)


def parse_product(raw: Any) -> Product | None:
    product = _obj(raw)
    product_id = _str(product.get("productId"))
    if product_id is None:
        return None
    item = _obj(next(iter(_list(product.get("items"))), None))
    fulfillment = _obj(item.get("fulfillment"))
    return Product(
        product_id=product_id,
        upc=_str(product.get("upc")),
        description=_str(product.get("description")) or "",
        brand=_str(product.get("brand")),
        categories=tuple(_strs(product.get("categories"))),
        page_uri=_str(product.get("productPageURI")),
        image=_image(product.get("images")),
        size=_str(item.get("size")),
        sold_by=_sold_by(item.get("soldBy")),
        price=_price(item.get("price")),
        stock_level=_str(_obj(item.get("inventory")).get("stockLevel")),
        in_store=_bool(_get_ci(fulfillment, "instore")),
        aisles=tuple(_aisle(raw) for raw in _list(product.get("aisleLocations"))),
    )


def parse_locations(body: Any) -> tuple[Location, ...]:
    """`{"data": [...]}` from a search, or `{"data": {...}}` from one location's details."""
    data = _obj(body).get("data")
    raws = _list(data) if isinstance(data, list) else [data]
    return tuple(location for raw in raws if (location := _location(raw)) is not None)


def parse_chains(body: Any) -> tuple[Chain, ...]:
    chains: list[Chain] = []
    for raw in _list(_obj(body).get("data")):
        chain = _obj(raw)
        name = _str(chain.get("name"))
        if name is not None:
            chains.append(
                Chain(
                    name=name,
                    domain=_str(chain.get("domain")),
                    division_numbers=tuple(_strs(chain.get("divisionNumbers"))),
                )
            )
    return tuple(chains)


def product_to_json(product: Product) -> str:
    """The cache's copy of a product (kroger_product_cache.payload). Exact: no floats."""
    price = product.price
    return json.dumps(
        {
            "product_id": product.product_id,
            "upc": product.upc,
            "description": product.description,
            "brand": product.brand,
            "categories": list(product.categories),
            "page_uri": product.page_uri,
            "image": [list(pair) for pair in product.image.sizes] if product.image else None,
            "size": product.size,
            "sold_by": product.sold_by.value if product.sold_by else None,
            "price": None
            if price is None
            else {
                "regular": price.regular,
                "promo": price.promo,
                "each_estimate": str(price.regular_each_estimate)
                if price.regular_each_estimate is not None
                else None,
                "effective": price.effective.isoformat() if price.effective else None,
                "expires": price.expires.isoformat() if price.expires else None,
            },
            "stock_level": product.stock_level,
            "in_store": product.in_store,
            "aisles": [
                {"number": a.number, "side": a.side, "description": a.description, "bay": a.bay}
                for a in product.aisles
            ],
        },
        separators=(",", ":"),
    )


def product_from_json(text: str) -> Product:
    data = _obj(json.loads(text))
    price = _obj(data.get("price"))
    image = [_list(pair) for pair in _list(data.get("image"))]
    estimate = _str(price.get("each_estimate"))
    return Product(
        product_id=str(data["product_id"]),
        upc=_str(data.get("upc")),
        description=_str(data.get("description")) or "",
        brand=_str(data.get("brand")),
        categories=tuple(_strs(data.get("categories"))),
        page_uri=_str(data.get("page_uri")),
        image=ProductImage(tuple((str(p[0]), str(p[1])) for p in image if len(p) == 2))
        if image
        else None,
        size=_str(data.get("size")),
        sold_by=_sold_by(data.get("sold_by")),
        price=Price(
            regular=_int(price.get("regular")),
            promo=_int(price.get("promo")),
            regular_each_estimate=Fraction(estimate) if estimate else None,
            effective=_when(price.get("effective")),
            expires=_when(price.get("expires")),
        )
        if price
        else None,
        stock_level=_str(data.get("stock_level")),
        in_store=_bool(data.get("in_store")),
        aisles=tuple(
            Aisle(
                number=_int(aisle.get("number")),
                side=_str(aisle.get("side")),
                description=_str(aisle.get("description")),
                bay=_int(aisle.get("bay")),
            )
            for aisle in (_obj(raw) for raw in _list(data.get("aisles")))
        ),
    )


def dollars_to_cents(value: Any) -> int | None:
    """Kroger dollars (Decimal, int or numeric text) → cents, half-up. None for missing or ≤ 0."""
    exact = _decimal(value)
    if exact is None or exact <= 0:
        return None
    return int((exact * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


# ---- pieces ---------------------------------------------------------------------------------


def _price(raw: Any) -> Price | None:
    price = _obj(raw)
    if not price:
        return None
    estimate = _decimal(price.get("regularPerUnitEstimate"))
    return Price(
        regular=dollars_to_cents(price.get("regular")),
        promo=dollars_to_cents(price.get("promo")),
        regular_each_estimate=Fraction(estimate) * 100 if estimate and estimate > 0 else None,
        effective=_when(price.get("effectiveDate")),
        expires=_when(price.get("expirationDate")),
    )


def _image(raw: Any) -> ProductImage | None:
    images = [_obj(image) for image in _list(raw)]
    if not images:
        return None
    chosen = next(
        (image for image in images if image.get("featured") is True),
        next((image for image in images if image.get("perspective") == "front"), images[0]),
    )
    sizes = tuple(
        (size, url)
        for entry in _list(chosen.get("sizes"))
        if (size := _str(_obj(entry).get("size"))) and (url := _str(_obj(entry).get("url")))
    )
    return ProductImage(sizes) if sizes else None


def _aisle(raw: Any) -> Aisle:
    aisle = _obj(raw)
    number = _int(aisle.get("number"))
    return Aisle(
        number=number if number is not None and number > 0 else None,
        side=_str(aisle.get("side")),
        description=_str(aisle.get("description")),
        bay=_int(aisle.get("bayNumber")),
    )


def _location(raw: Any) -> Location | None:
    location = _obj(raw)
    location_id = _str(location.get("locationId"))
    if location_id is None:
        return None
    address = _obj(location.get("address"))
    return Location(
        location_id=location_id,
        chain=_str(location.get("chain")) or "",
        name=_str(location.get("name")) or "",
        address_line1=_str(address.get("addressLine1")),
        address_line2=_str(address.get("addressLine2")),
        city=_str(address.get("city")),
        state=_str(address.get("state")),
        zip_code=_str(address.get("zipCode")),
        timezone=_str(_obj(location.get("hours")).get("timezone")),
        departments=tuple(
            name
            for department in _list(location.get("departments"))
            if (name := _str(_obj(department).get("name"))) is not None
        ),
    )


def _sold_by(value: Any) -> SoldBy | None:
    text = _str(value)
    if text is None:
        return None
    try:
        return SoldBy(text.upper())
    except ValueError:
        return None


def _when(value: Any) -> datetime | date | None:
    """An ISO date or datetime, alone or as {"value": ..., "timezone": ...}."""
    holder = _obj(value)
    text = _str(holder.get("value")) if holder else _str(value)
    if text is None:
        return None
    try:
        if len(text) == 10:
            return date.fromisoformat(text)
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is not None:
        return moment
    zone_name = _str(holder.get("timezone")) if holder else None
    try:
        return moment.replace(tzinfo=ZoneInfo(zone_name) if zone_name else UTC)
    except ZoneInfoNotFoundError, ValueError:
        return moment.replace(tzinfo=UTC)


# ---- JSON helpers: everything from Kroger is untrusted and may be missing --------------------


def _obj(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return cast(list[Any], value) if isinstance(value, list) else []


def _str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _strs(value: Any) -> Iterable[str]:
    return (text for item in _list(value) if (text := _str(item)) is not None)


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = _str(value)
    return int(text) if text is not None and text.isdigit() else None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float):
        raise TypeError("parse Kroger JSON with parse_float=Decimal; floats never touch money")
    if isinstance(value, Decimal | int):
        return Decimal(value)
    text = _str(value)
    if text is None:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _get_ci(mapping: dict[str, Any], key: str) -> Any:
    """Kroger sends both `inStore` and `instore`; look keys up case-insensitively."""
    lowered = key.lower()
    return next((value for name, value in mapping.items() if name.lower() == lowered), None)
