"""The real Kroger client (docs/PLAN.md §7.2).

* One `httpx.AsyncClient`: connect 5 s, read 10 s, no redirects, `User-Agent: DinnerBell/<v>`.
* The app token (client credentials, `product.compact`) lives in memory. It is refreshed when
  under 60 s remain, single-flight, with a re-check inside the lock.
* GETs and the token POST retry connect errors, timeouts and 500/502/503/504: 3 attempts with
  full-jitter backoff (0.5 s base, 4 s cap), honoring `Retry-After` up to 10 s.
* A 401 forces one token refresh and one retry. A 429 blocks the bucket (usage.py).
* JSON is parsed with `parse_float=Decimal`, so prices are exact before they become cents.
* Logs carry the bucket, status and attempt only: never terms, tokens, IDs or payloads.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any, cast
from urllib.parse import quote

import httpx

from dinnerbell.core.clock import Clock
from dinnerbell.core.logging import get_logger
from dinnerbell.core.version import build_info
from dinnerbell.kroger.cachepolicy import NOT_STORABLE, CachePolicy, cache_policy
from dinnerbell.kroger.client import (
    Fetched,
    KrogerAuthError,
    KrogerDailyLimitError,
    KrogerRequestError,
    KrogerUnavailableError,
)
from dinnerbell.kroger.parse import (
    Chain,
    Location,
    Product,
    parse_chains,
    parse_locations,
    parse_products,
)
from dinnerbell.kroger.usage import Bucket, UsageGuard

log = get_logger(__name__)

API_BASE = "https://api.kroger.com/v1"
IMAGE_BASE = "https://www.kroger.com/product/images"  # the CSP's img-src allows exactly this
TOKEN_PATH = "/connect/oauth2/token"  # noqa: S105 - a URL path, not a secret
TOKEN_SCOPE = "product.compact"  # noqa: S105 - an OAuth scope name, not a secret
TOKEN_MARGIN = timedelta(seconds=60)
RETRY_STATUSES = frozenset({500, 502, 503, 504})
MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 0.5
BACKOFF_CAP_S = 4.0
RETRY_AFTER_MAX_S = 10.0
MAX_BATCH = 50
TRANSIENT_ERRORS = (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError)

type Observer = Callable[[str, httpx.Response], None]
type Sleep = Callable[[float], Awaitable[None]]


class LiveKroger:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        usage: UsageGuard,
        clock: Clock,
        transport: httpx.AsyncBaseTransport | None = None,
        base_url: str = API_BASE,
        sleep: Sleep = asyncio.sleep,
        rng: random.Random | None = None,
        observer: Observer | None = None,
    ) -> None:
        if transport is None and _under_pytest():
            raise RuntimeError("the live Kroger client needs KROGER_LIVE=1 under pytest")
        self._basic = httpx.BasicAuth(client_id, client_secret)
        self._http = httpx.AsyncClient(
            base_url=base_url,
            transport=transport,
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=False,
            headers={
                "User-Agent": f"DinnerBell/{build_info().version}",
                "Accept": "application/json",
            },
        )
        self._usage = usage
        self._clock = clock
        self._sleep = sleep
        self._rng = rng or random.SystemRandom()
        self._observer = observer
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._token_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    def image_url(self, product_id: str) -> str:
        return f"{IMAGE_BASE}/medium/front/{quote(product_id, safe='')}"

    # ---- the API ----------------------------------------------------------------------------

    async def locations(self, zip_code: str, *, limit: int = 20) -> Fetched[tuple[Location, ...]]:
        params = {"filter.zipCode.near": zip_code, "filter.limit": str(limit)}
        response = await self._get(Bucket.LOCATIONS, "/locations", params)
        return Fetched(parse_locations(self._json(response)), self._policy(response))

    async def location(self, location_id: str) -> Fetched[Location | None]:
        path = f"/locations/{quote(location_id, safe='')}"
        response = await self._get(Bucket.LOCATIONS, path, {}, allow_404=True)
        if response.status_code == 404:
            return Fetched(None, NOT_STORABLE)
        found = parse_locations(self._json(response))
        return Fetched(found[0] if found else None, self._policy(response))

    async def chains(self) -> Fetched[tuple[Chain, ...]]:
        response = await self._get(Bucket.CHAINS, "/chains", {})
        return Fetched(parse_chains(self._json(response)), self._policy(response))

    async def search_products(
        self, term: str, location_id: str, *, limit: int = 20, start: int = 1
    ) -> Fetched[tuple[Product, ...]]:
        params = {
            "filter.term": term,
            "filter.locationId": location_id,
            "filter.limit": str(limit),
            "filter.start": str(start),
        }
        response = await self._get(Bucket.PRODUCTS, "/products", params)
        return Fetched(parse_products(self._json(response)), self._policy(response))

    async def get_product(self, product_id: str, location_id: str) -> Fetched[Product | None]:
        path = f"/products/{quote(product_id, safe='')}"
        params = {"filter.locationId": location_id}
        response = await self._get(Bucket.PRODUCTS, path, params, allow_404=True)
        if response.status_code == 404:
            return Fetched(None, NOT_STORABLE)
        products = parse_products(self._json(response))
        return Fetched(products[0] if products else None, self._policy(response))

    async def get_products(
        self, product_ids: Sequence[str], location_id: str
    ) -> Fetched[tuple[Product, ...]]:
        if not 1 <= len(product_ids) <= MAX_BATCH:
            raise ValueError(f"ask for 1 to {MAX_BATCH} products at a time")
        params = {
            "filter.productId": ",".join(product_ids),
            "filter.locationId": location_id,
            "filter.limit": str(len(product_ids)),
        }
        response = await self._get(Bucket.PRODUCTS, "/products", params)
        return Fetched(parse_products(self._json(response)), self._policy(response))

    # ---- requests ---------------------------------------------------------------------------

    async def _get(
        self,
        bucket: Bucket,
        path: str,
        params: Mapping[str, str],
        *,
        allow_404: bool = False,
    ) -> httpx.Response:
        await self._usage.check(bucket)
        attempt = 1
        refreshed = False
        while True:
            token = await self._app_token()
            try:
                response = await self._http.get(
                    path, params=params, headers={"Authorization": f"Bearer {token}"}
                )
            except TRANSIENT_ERRORS as exc:
                await self._retry_or_raise(bucket, attempt, None, type(exc).__name__)
                attempt += 1
                continue
            self._observe(bucket, response)
            status = response.status_code
            blocked_until = await self._usage.record(
                bucket, status, reset_after=_reset_after(response.headers.get("ratelimit-reset"))
            )
            log.info("kroger.call", api=bucket, status=status, attempt=attempt)
            if status == 429:
                raise KrogerDailyLimitError(blocked_until or self._clock.now() + timedelta(hours=1))
            if status == 401 and not refreshed:
                refreshed = True
                self._forget(token)
                continue
            if status in RETRY_STATUSES:
                await self._retry_or_raise(
                    bucket, attempt, response.headers.get("retry-after"), str(status)
                )
                attempt += 1
                continue
            if status == 404 and allow_404:
                return response
            if status in (401, 403):
                raise KrogerAuthError("Kroger refused this app's access to the API")
            if status >= 400:
                raise KrogerRequestError(status)
            return response

    async def _retry_or_raise(
        self, label: str, attempt: int, retry_after: str | None, reason: str
    ) -> None:
        delay = self._delay(attempt, retry_after)
        if attempt >= MAX_ATTEMPTS or delay is None:
            log.warning("kroger.unavailable", api=label, reason=reason, attempts=attempt)
            # `from None`: httpx's own exception can carry the request, and the URL holds terms.
            raise KrogerUnavailableError(f"Kroger isn't answering ({reason})") from None
        await self._sleep(delay)

    def _delay(self, attempt: int, retry_after: str | None) -> float | None:
        """Full jitter; Retry-After wins when longer, and over 10 s means "give up for now"."""
        jitter = self._rng.uniform(0, min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** (attempt - 1)))
        wait = _retry_after_seconds(retry_after, self._clock.now())
        if wait is None:
            return jitter
        if wait > RETRY_AFTER_MAX_S:
            return None
        return max(jitter, wait)

    # ---- the app token ----------------------------------------------------------------------

    async def _app_token(self) -> str:
        if (token := self._fresh_token()) is not None:
            return token
        async with self._token_lock:
            if (token := self._fresh_token()) is not None:
                return token  # another request refreshed it while we waited
            token, lifetime = await self._fetch_token()
            self._token = token
            self._token_expires = self._clock.now() + lifetime
            return token

    def _fresh_token(self) -> str | None:
        if self._token is None or self._token_expires is None:
            return None
        if self._token_expires - self._clock.now() <= TOKEN_MARGIN:
            return None
        return self._token

    def _forget(self, token: str) -> None:
        if self._token == token:  # a concurrent refresh may already have replaced it
            self._token = None
            self._token_expires = None

    async def _fetch_token(self) -> tuple[str, timedelta]:
        attempt = 1
        while True:
            try:
                response = await self._http.post(
                    TOKEN_PATH,
                    data={"grant_type": "client_credentials", "scope": TOKEN_SCOPE},
                    auth=self._basic,
                )
            except TRANSIENT_ERRORS as exc:
                await self._retry_or_raise("token", attempt, None, type(exc).__name__)
                attempt += 1
                continue
            self._observe("token", response)
            status = response.status_code
            if status in RETRY_STATUSES:
                await self._retry_or_raise(
                    "token", attempt, response.headers.get("retry-after"), str(status)
                )
                attempt += 1
                continue
            if status in (400, 401, 403):
                log.warning("kroger.token_refused", status=status)
                raise KrogerAuthError("Kroger refused the client ID or secret")
            if status >= 400:
                raise KrogerRequestError(status)
            body = self._json(response)
            fields = cast(dict[str, Any], body) if isinstance(body, dict) else {}
            token = fields.get("access_token")
            lifetime = fields.get("expires_in")
            if not isinstance(token, str) or not token or not isinstance(lifetime, int):
                raise KrogerUnavailableError("Kroger sent a token response we couldn't read")
            return token, timedelta(seconds=lifetime)

    # ---- helpers ----------------------------------------------------------------------------

    def _json(self, response: httpx.Response) -> Any:
        try:
            return json.loads(response.content, parse_float=Decimal)
        except ValueError:
            raise KrogerUnavailableError("Kroger sent a response that isn't JSON") from None

    def _policy(self, response: httpx.Response) -> CachePolicy:
        return cache_policy(response.headers, self._clock.now())

    def _observe(self, label: str, response: httpx.Response) -> None:
        if self._observer is not None:
            self._observer(label, response)


def _retry_after_seconds(value: str | None, now: datetime) -> float | None:
    if value is None or not value.strip():
        return None
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        when = parsedate_to_datetime(text)
    except TypeError, ValueError:
        return None
    if when.tzinfo is None:
        return None
    return max(0.0, (when - now).total_seconds())


def _reset_after(value: str | None) -> timedelta | None:
    """Kroger's `ratelimit-reset`: seconds until the daily window resets (seen on Locations)."""
    if value is None or not value.strip().isdigit():
        return None
    return timedelta(seconds=int(value.strip()))


def _under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ and os.environ.get("KROGER_LIVE") != "1"
