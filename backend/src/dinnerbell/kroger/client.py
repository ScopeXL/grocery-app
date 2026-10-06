"""The one interface the app uses to talk to Kroger, and its errors (docs/PLAN.md §7.2).

`KROGER_MODE` picks the implementation: `live.LiveKroger` or `fake.FakeKroger`. Cart and
account-linking methods arrive with M5.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
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

    async def aclose(self) -> None: ...
