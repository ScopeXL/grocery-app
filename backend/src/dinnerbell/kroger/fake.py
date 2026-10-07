"""Synthetic Kroger data for development, tests, e2e runs and screenshots (docs/PLAN.md §7.6).

The fixtures copy the real response *shapes*, quirks included (soldBy casing, inStore/instore,
a promo of 0, placeholder aisles, a fuel center), but every name, ID, address and price is made
up. Product photos are small SVGs served by `/api/kroger/fake-images/…`.

Two magic inputs exercise quiet states: the ZIP `00000` finds no stores, and the search term
`dailylimit` behaves as if Kroger's daily limit were used up.

Connect Kroger goes through a demo sign-in page (`/api/kroger/fake-authorize`) instead of
Kroger's, but the rest is checked as Kroger would: codes and refresh tokens are single-use, the
PKCE verifier must match, and access tokens expire after 30 minutes. Tokens carry what they
need, so a restarted dev server still accepts them. Cart adds land in `cart`, in memory; tests
can make an add fail (`cart_failures`) or the next refresh fail (`refresh_failure`).

Sale dates in the fixtures are written for FIXTURE_DAY and move with the clock, so the fake
store's sales are always current: tests on a fixed clock see the dates as written, and e2e runs
on the real clock see the same sales, as many days ahead.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import cache
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from dinnerbell.core.clock import Clock
from dinnerbell.core.crypto import b64url
from dinnerbell.kroger.cachepolicy import NOT_STORABLE, CachePolicy
from dinnerbell.kroger.client import (
    CartItem,
    Fetched,
    KrogerCustomerAuthError,
    KrogerDailyLimitError,
    KrogerError,
    KrogerGrantError,
    TokenGrant,
)
from dinnerbell.kroger.parse import (
    Chain,
    Location,
    Price,
    Product,
    parse_chains,
    parse_locations,
    parse_products,
)

FIXTURES = Path(__file__).parent / "fixtures"
IMAGE_BASE = "/api/kroger/fake-images"
NO_STORES_ZIP = "00000"
DAILY_LIMIT_TERM = "dailylimit"
FIXTURE_DAY = date(2026, 10, 6)  # the day the fixtures' sale dates were written for
AUTHORIZE_PATH = "/api/kroger/fake-authorize"
TOKEN_LIFETIME = timedelta(seconds=1800)  # like Kroger's
CART_SCOPE = "cart.basic:write"


class FakeKroger:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._products = _products()
        self._locations = _locations()
        self._store_ids = {location.location_id for location in self._locations}
        self._used: set[str] = set()  # sign-in codes and refresh tokens already traded
        self.cart: list[CartItem] = []
        self.cart_failures: dict[str, KrogerError] = {}  # upc -> what adding it raises
        self.refresh_failure: KrogerError | None = None  # what the next refresh raises
        self.rotate_refresh = True

    async def aclose(self) -> None:
        return None

    def reset_account(self) -> None:
        self._used.clear()
        self.cart.clear()
        self.cart_failures.clear()
        self.refresh_failure = None
        self.rotate_refresh = True

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

    # ---- a customer's account and cart -------------------------------------------------------

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return f"{AUTHORIZE_PATH}?{urlencode({'state': state, 'code_challenge': code_challenge})}"

    def issue_code(self, code_challenge: str) -> str:
        """The demo sign-in page's Allow: a single-use code bound to the PKCE challenge."""
        return f"demo.{code_challenge}.{secrets.token_urlsafe(8)}"

    async def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> TokenGrant:
        parts = code.split(".")
        if len(parts) != 3 or parts[0] != "demo" or code in self._used:
            raise KrogerGrantError("unknown or used code")
        self._used.add(code)
        if b64url(hashlib.sha256(code_verifier.encode()).digest()) != parts[1]:
            raise KrogerGrantError("the code verifier doesn't match")
        return self._grant(rotate=True)

    async def refresh(self, refresh_token: str) -> TokenGrant:
        if self.refresh_failure is not None:
            failure, self.refresh_failure = self.refresh_failure, None
            raise failure
        if not refresh_token.startswith("demo-refresh.") or refresh_token in self._used:
            raise KrogerGrantError("unknown or used refresh token")
        if self.rotate_refresh:
            self._used.add(refresh_token)
        return self._grant(rotate=self.rotate_refresh)

    async def add_to_cart(self, access_token: str, items: Sequence[CartItem]) -> None:
        if not self._access_valid(access_token):
            raise KrogerCustomerAuthError("the access token is unknown or expired")
        for item in items:
            failure = self.cart_failures.get(item.upc)
            if failure is not None:
                raise failure
        self.cart.extend(items)

    def _grant(self, *, rotate: bool) -> TokenGrant:
        expires = int((self._clock.now() + TOKEN_LIFETIME).timestamp())
        return TokenGrant(
            access_token=f"demo-access.{expires}.{secrets.token_urlsafe(12)}",
            expires_in=TOKEN_LIFETIME,
            refresh_token=f"demo-refresh.{secrets.token_urlsafe(12)}" if rotate else None,
            scope=CART_SCOPE,
        )

    def _access_valid(self, token: str) -> bool:
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != "demo-access" or not parts[1].isdigit():
            return False
        return self._clock.now() < datetime.fromtimestamp(int(parts[1]), UTC)

    def _at(self, location_id: str, product: Product) -> Product:
        """Like Kroger, an unknown store gets no price, stock or aisle."""
        if location_id not in self._store_ids:
            return replace(product, price=None, stock_level=None, in_store=None, aisles=())
        days = timedelta(days=(self._clock.now().astimezone(UTC).date() - FIXTURE_DAY).days)
        if product.price is None or not days:
            return product
        return replace(product, price=_moved(product.price, days))

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


def _moved(price: Price, days: timedelta) -> Price:
    return replace(
        price,
        effective=None if price.effective is None else price.effective + days,
        expires=None if price.expires is None else price.expires + days,
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
