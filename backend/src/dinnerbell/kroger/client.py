"""The one interface the app uses to talk to Kroger, and its errors (docs/PLAN.md §7.2).

`KROGER_MODE` picks the implementation: `live.LiveKroger` or `fake.FakeKroger`. Products and
stores use the app's own token; the cart uses a customer's, from Connect Kroger (§7.5).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from dinnerbell.kroger.cachepolicy import CachePolicy
from dinnerbell.kroger.parse import Chain, Location, Product


@dataclass(frozen=True, slots=True)
class Fetched[T]:
    """A parsed response plus what its cache headers let us keep."""

    data: T
    cache: CachePolicy


class KrogerError(Exception):
    """Base class. Messages are safe to log: never terms, tokens, IDs or payloads."""


class KrogerUnavailableError(KrogerError):
    """Kroger couldn't be reached, or kept failing after retries."""


class KrogerAuthError(KrogerError):
    """Kroger refused the client ID or secret, or this app isn't allowed to use the API."""


class KrogerRequestError(KrogerError):
    """Kroger rejected the request itself (a 4xx other than 401, 403, 404 and 429)."""

    def __init__(self, status: int) -> None:
        super().__init__(f"Kroger rejected the request ({status})")
        self.status = status


class KrogerDailyLimitError(KrogerError):
    """The day's limit is used up; nothing goes out until `retry_at`."""

    def __init__(self, retry_at: datetime) -> None:
        super().__init__("Kroger's daily limit is used up")
        self.retry_at = retry_at


class KrogerGrantError(KrogerError):
    """Kroger refused a customer's sign-in code or refresh token: the account must connect again."""


class KrogerCustomerAuthError(KrogerError):
    """Kroger refused the customer's access token (401) on a cart call."""


class KrogerCartUnknownError(KrogerError):
    """A cart add went out but no clear answer came back: it may or may not be in the cart."""


class Modality(StrEnum):
    PICKUP = "PICKUP"
    DELIVERY = "DELIVERY"


@dataclass(frozen=True, slots=True)
class TokenGrant:
    """A customer's tokens from Kroger's token endpoint (a sign-in code, or a refresh)."""

    access_token: str
    expires_in: timedelta
    refresh_token: str | None  # None when Kroger didn't send a new one: keep the old
    scope: str | None


@dataclass(frozen=True, slots=True)
class CartItem:
    upc: str
    quantity: int  # whole units: Kroger's cart takes integers
    modality: Modality


class KrogerApi(Protocol):
    async def locations(self, zip_code: str, *, limit: int = 20) -> Fetched[tuple[Location, ...]]:
        """Stores near a ZIP code, nearest first. Fuel centers are included; callers drop them."""
        ...

    async def location(self, location_id: str) -> Fetched[Location | None]: ...

    async def chains(self) -> Fetched[tuple[Chain, ...]]: ...

    async def search_products(
        self, term: str, location_id: str, *, limit: int = 20, start: int = 1
    ) -> Fetched[tuple[Product, ...]]:
        """Kroger's fuzzy search: 3+ characters, at most 8 words, with the store's prices."""
        ...

    async def get_product(self, product_id: str, location_id: str) -> Fetched[Product | None]: ...

    async def get_products(
        self, product_ids: Sequence[str], location_id: str
    ) -> Fetched[tuple[Product, ...]]:
        """Up to 50 products by ID in one call."""
        ...

    def image_url(self, product_id: str) -> str:
        """A product's front photo, without a call: Kroger's image URLs follow the product ID."""
        ...

    # ---- a customer's account (Connect Kroger) and cart ---------------------------------------

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        """Where a phone goes to sign in to Kroger and allow cart access (PKCE S256)."""
        ...

    async def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> TokenGrant:
        """Trade the callback's code for the customer's tokens. Retried only when the request
        provably never left (a connect error)."""
        ...

    async def refresh(self, refresh_token: str) -> TokenGrant:
        """New tokens; Kroger usually rotates the refresh token too. Same retry rule."""
        ...

    async def add_to_cart(self, access_token: str, items: Sequence[CartItem]) -> None:
        """`PUT /cart/add`. **Never retried**: an add that may have landed must not land twice.

        Raises KrogerUnavailableError when the request never reached Kroger (safe to send
        again), KrogerCartUnknownError when it went out but no clear answer came back,
        KrogerCustomerAuthError on a 401, KrogerAuthError on a 403, KrogerDailyLimitError on a
        429 and KrogerRequestError on any other 4xx.
        """
        ...

    async def aclose(self) -> None: ...
