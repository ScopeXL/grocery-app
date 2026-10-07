"""Synthetic Kroger data for development, tests, e2e runs and screenshots (docs/PLAN.md §7.6).

The fixtures copy the real response *shapes*, quirks included (soldBy casing, inStore/instore,
a promo of 0, placeholder aisles, a fuel center), but every name, ID, address and price is made
up. Product photos are small SVGs served by `/api/kroger/fake-images/…`.

Two magic inputs exercise quiet states: the ZIP `00000` finds no stores, and the search term
`dailylimit` behaves as if Kroger's daily limit were used up.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from functools import cache
from html import escape
from pathlib import Path
from typing import Any

from dinnerbell.core.clock import Clock
from dinnerbell.kroger.cachepolicy import NOT_STORABLE, CachePolicy
from dinnerbell.kroger.client import Fetched, KrogerDailyLimitError
from dinnerbell.kroger.parse import (
    Chain,
    Location,
    Product,
    parse_chains,
    parse_locations,
    parse_products,
)

FIXTURES = Path(__file__).parent / "fixtures"
IMAGE_BASE = "/api/kroger/fake-images"
NO_STORES_ZIP = "00000"
DAILY_LIMIT_TERM = "dailylimit"


class FakeKroger:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._products = _products()
        self._locations = _locations()
        self._store_ids = {location.location_id for location in self._locations}

    async def aclose(self) -> None:
        return None

    def image_url(self, product_id: str) -> str:
        return f"{IMAGE_BASE}/{product_id}.svg"

    async def locations(self, zip_code: str, *, limit: int = 20) -> Fetched[tuple[Location, ...]]:
        found = () if zip_code == NO_STORES_ZIP else self._locations[:limit]
        return Fetched(found, self._policy())

    async def location(self, location_id: str) -> Fetched[Location | None]:
        found = next((s for s in self._locations if s.location_id == location_id), None)
        return Fetched(found, self._policy())

    async def chains(self) -> Fetched[tuple[Chain, ...]]:
        return Fetched(parse_chains({"data": _load("chains.json")}), self._policy())

    async def search_products(
        self, term: str, location_id: str, *, limit: int = 20, start: int = 1
    ) -> Fetched[tuple[Product, ...]]:
        words = term.casefold().split()
        if words == [DAILY_LIMIT_TERM]:
            raise KrogerDailyLimitError(self._clock.now() + timedelta(hours=2))
        matches = [
            product
            for product in self._products
            if words and all(word in _haystack(product) for word in words)
        ]
        page = matches[start - 1 : start - 1 + limit]
        return Fetched(tuple(self._at(location_id, p) for p in page), self._policy())

    async def get_product(self, product_id: str, location_id: str) -> Fetched[Product | None]:
        product = next((p for p in self._products if product_id in (p.product_id, p.upc)), None)
        found = self._at(location_id, product) if product else None
        return Fetched(found, self._policy())

    async def get_products(
        self, product_ids: Sequence[str], location_id: str
    ) -> Fetched[tuple[Product, ...]]:
        wanted = set(product_ids)
        found = tuple(self._at(location_id, p) for p in self._products if p.product_id in wanted)
        return Fetched(found, self._policy())

    def _at(self, location_id: str, product: Product) -> Product:
        """Like Kroger, an unknown store gets no price, stock or aisle."""
        if location_id in self._store_ids:
            return product
        return replace(product, price=None, stock_level=None, in_store=None, aisles=())

    def _policy(self) -> CachePolicy:
        """Like Kroger (smoke test, 2026-10-06): no freshness headers, so nothing is kept."""
        return NOT_STORABLE


def image_svg(name: str) -> str | None:
    """A plain placeholder photo for a fixture product (or None if there's no such product)."""
    product_id = name.removesuffix(".svg")
    product = next((p for p in _products() if p.product_id == product_id), None)
    if product is None or product.image is None:
        return None  # like Kroger: a product without photos has no image to fetch
    label = escape(product.description.removeprefix("Sample ").split()[-1])
    hue = int(product_id) * 47 % 360
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" role="img" '
        f'aria-label="{escape(product.description)}">'
        f'<rect width="240" height="240" fill="hsl({hue} 45% 88%)"/>'
        f'<rect x="60" y="40" width="120" height="150" rx="16" fill="hsl({hue} 40% 55%)"/>'
        '<text x="120" y="222" font-family="sans-serif" font-size="22" text-anchor="middle" '
        f'fill="hsl({hue} 50% 22%)">{label}</text></svg>'
    )


def _haystack(product: Product) -> str:
    return " ".join((product.description, product.brand or "", *product.categories)).casefold()


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(), parse_float=Decimal)


@cache
def _products() -> tuple[Product, ...]:
    return parse_products({"data": _load("products.json")})


@cache
def _locations() -> tuple[Location, ...]:
    return parse_locations({"data": _load("locations.json")})
