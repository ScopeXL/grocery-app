"""`dinnerbell smoke-kroger`: a few real calls that answer PLAN §13's open Kroger questions.

Run it with `just smoke-kroger`, which sets KROGER_LIVE=1 and loads the local .env (the keys and
KROGER_SMOKE_ZIP). It prints status codes, cache and rate headers, header names, field types,
counts and image URL prefixes: what docs/KROGER.md records. It never prints the ZIP, the store,
product names, IDs, prices, tokens or payloads.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any, TextIO, cast
from urllib.parse import urlsplit

import httpx

from dinnerbell.core.clock import SystemClock
from dinnerbell.core.version import build_info
from dinnerbell.kroger.client import KrogerError
from dinnerbell.kroger.live import LiveKroger
from dinnerbell.kroger.parse import Product
from dinnerbell.kroger.usage import MemoryUsageStore, UsageGuard

SEARCH_TERM = "milk"  # generic on purpose; nothing about the household
CACHE_HEADERS = ("cache-control", "expires", "age", "pragma", "vary", "etag", "last-modified")
IMAGE_HEADERS = (
    "content-type",
    "cache-control",
    "access-control-allow-origin",
    "vary",
    "cross-origin-resource-policy",
    "timing-allow-origin",
)
RATE_WORDS = ("rate", "limit", "quota", "retry", "remaining")

type Say = Callable[[str], None]


async def run(
    environ: Mapping[str, str],
    out: TextIO,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    def say(line: str = "") -> None:
        print(line, file=out)

    if environ.get("KROGER_LIVE") != "1":
        say("Skipped: set KROGER_LIVE=1 to call the real Kroger API (`just smoke-kroger` does).")
        return 0
    client_id = environ.get("KROGER_CLIENT_ID", "").strip()
    secret = environ.get("KROGER_CLIENT_SECRET", "").strip()
    zip_code = environ.get("KROGER_SMOKE_ZIP", "").strip()
    missing = [
        name
        for name, value in (
            ("KROGER_CLIENT_ID", client_id),
            ("KROGER_CLIENT_SECRET", secret),
            ("KROGER_SMOKE_ZIP", zip_code),
        )
        if not value
    ]
    if missing:
        say(f"Skipped: add {', '.join(missing)} to the local .env.")
        return 0
    if not re.fullmatch(r"\d{5}", zip_code):
        say("Skipped: KROGER_SMOKE_ZIP must be a 5-digit ZIP code.")
        return 0

    seen: dict[str, httpx.Response] = {}
    clock = SystemClock()
    kroger = LiveKroger(
        client_id,
        secret,
        usage=UsageGuard(MemoryUsageStore(), clock),
        clock=clock,
        transport=transport,
        observer=lambda label, response: seen.__setitem__(label, response),
    )
    answers: dict[str, str] = {}
    try:
        stores = await kroger.locations(zip_code, limit=10)
        _report(say, "token", seen.get("token"))
        lifetime = _obj(_body(seen.get("token"))).get("expires_in")
        say(f"token lifetime (s): {lifetime if isinstance(lifetime, int) else 'unknown'}")

        _report(say, "locations near the ZIP (limit 10)", seen.get("locations"))
        raw_stores = _list(_obj(_body(seen.get("locations"))).get("data"))
        fuel = sum(1 for store in stores.data if store.is_fuel_center)
        say(f"results: {len(stores.data)}; fuel centers: {fuel}")
        first_store = next((s for s in stores.data if not s.is_fuel_center), None)
        first_raw = next(
            (
                s
                for s in raw_stores
                if _obj(s).get("locationId") == getattr(first_store, "location_id", None)
            ),
            None,
        )
        say(f"location fields: {_shape(first_raw)}")
        answers["locations cache"] = _cache_text(seen.get("locations"))
        if first_store is None:
            say("Stopped: no store (other than fuel centers) near that ZIP.")
            return 1

        chains = await kroger.chains()
        _report(say, "chains", seen.get("chains"))
        with_domain = sum(1 for chain in chains.data if chain.domain)
        say(f"results: {len(chains.data)}; with a domain: {with_domain}")

        found = await kroger.search_products(SEARCH_TERM, first_store.location_id, limit=5)
        _report(
            say,
            f'product search "{SEARCH_TERM}" at the first store (limit 5)',
            seen.get("products"),
        )
        raw_products = _list(_obj(_body(seen.get("products"))).get("data"))
        say(_product_counts(found.data))
        say(f"product fields: {_shape(raw_products[0] if raw_products else None)}")
        prefixes = sorted({_image_prefix(url) for p in found.data for url in _image_urls(p)})
        say(f"image URL prefixes: {', '.join(prefixes) or 'none'}")
        answers["products cache (search)"] = _cache_text(seen.get("products"))
        answers["image hosts"] = ", ".join(prefixes) or "none"
        if not found.data:
            say("Stopped: the search found nothing to look up by ID.")
            return 1

        one = await kroger.get_product(found.data[0].product_id, first_store.location_id)
        _report(say, "one product by ID, with the store", seen.get("products"))
        has_price = bool(one.data and one.data.price and one.data.price.regular)
        has_aisle = bool(one.data and one.data.aisles)
        say(f"has a price: {_yes(has_price)}; has an aisle: {_yes(has_aisle)}")
        answers["products cache (by ID)"] = _cache_text(seen.get("products"))

        ids = [product.product_id for product in found.data[:3]]
        batch = await kroger.get_products(ids, first_store.location_id)
        _report(
            say,
            f"{len(ids)} products by filter.productId, with filter.locationId",
            seen.get("products"),
        )
        priced = sum(1 for p in batch.data if p.price and p.price.regular)
        with_aisles = sum(1 for p in batch.data if p.aisles)
        say(f"returned: {len(batch.data)}; with a price: {priced}; with aisle info: {with_aisles}")
        all_priced = priced == len(batch.data) and priced > 0
        answers["batch includes store prices"] = (
            f"{_yes(all_priced)} ({priced} of {len(batch.data)} priced)"
        )

        image_url = next((url for p in found.data for url in _image_urls(p)), None)
        if image_url:
            await _report_image(say, image_url, transport)
    except KrogerError as exc:
        say(f"Stopped: {type(exc).__name__}: {exc}")
        return 1
    finally:
        await kroger.aclose()

    say("")
    say("== answers for docs/KROGER.md ==")
    for question, answer in answers.items():
        say(f"{question}: {answer}")
    say("429: not observed (this check never provokes one)")
    return 0


# ---- report pieces --------------------------------------------------------------------------


def _report(say: Say, title: str, response: httpx.Response | None) -> None:
    say("")
    say(f"== {title} ==")
    if response is None:
        say("no response recorded")
        return
    say(f"status: {response.status_code}")
    say(f"cache: {_cache_text(response)}")
    rates = [
        f"{name}: {value}"
        for name, value in response.headers.items()
        if any(word in name.lower() for word in RATE_WORDS)
    ]
    say(f"rate headers: {'; '.join(rates) or 'none'}")
    say(f"header names: {', '.join(sorted({name.lower() for name in response.headers}))}")


def _cache_text(response: httpx.Response | None) -> str:
    if response is None:
        return "no response"
    found = [
        f"{name}: {response.headers[name]}" for name in CACHE_HEADERS if name in response.headers
    ]
    return "; ".join(found) or "no cache headers"


async def _report_image(say: Say, url: str, transport: httpx.AsyncBaseTransport | None) -> None:
    say("")
    say("== one product image, fetched with an Origin header ==")
    headers = {
        "Origin": "https://dinner.example.com",
        "User-Agent": f"DinnerBell/{build_info().version}",
    }
    try:
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as http:
            response = await http.get(url, headers=headers)
    except httpx.HTTPError as exc:
        say(f"couldn't fetch it: {type(exc).__name__}")
        return
    say(f"status: {response.status_code}")
    for name in IMAGE_HEADERS:
        say(f"{name}: {response.headers.get(name, 'absent')}")


def _product_counts(products: tuple[Product, ...]) -> str:
    priced = sum(1 for p in products if p.price and p.price.regular)
    promo = sum(1 for p in products if p.price and p.price.promo)
    aisle = sum(1 for p in products if p.aisle is not None)
    placeholder = sum(1 for p in products if p.aisles and p.aisle is None)
    sold_by = sorted({p.sold_by.value if p.sold_by else "missing" for p in products})
    return (
        f"results: {len(products)}; with a price: {priced}; with a promo: {promo}; "
        f"with an aisle: {aisle}; placeholder aisles only: {placeholder}; "
        f"soldBy values: {', '.join(sold_by) or 'none'}"
    )


def _image_urls(product: Product) -> list[str]:
    return [url for _, url in product.image.sizes] if product.image else []


def _image_prefix(url: str) -> str:
    """Scheme, host and path with ID-like segments hidden: never a product ID."""
    parts = urlsplit(url)
    segments = [
        "<id>" if re.fullmatch(r"[0-9A-Za-z_-]*\d{4,}[0-9A-Za-z_-]*", s) else s
        for s in parts.path.split("/")
    ]
    return f"{parts.scheme}://{parts.netloc}{'/'.join(segments)}"


def _shape(value: Any, depth: int = 0) -> Any:
    """The structure of a JSON value with every value replaced by its type."""
    if depth > 5:
        return "…"
    if isinstance(value, dict):
        mapping = cast(dict[str, Any], value)
        return {key: _shape(item, depth + 1) for key, item in sorted(mapping.items())}
    if isinstance(value, list):
        items = cast(list[Any], value)
        return [_shape(items[0], depth + 1)] if items else []
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, Decimal):
        return "decimal"
    return type(value).__name__


def _body(response: httpx.Response | None) -> Any:
    if response is None:
        return None
    try:
        return json.loads(response.content, parse_float=Decimal)
    except ValueError:
        return None


def _obj(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return cast(list[Any], value) if isinstance(value, list) else []


def _yes(value: bool) -> str:
    return "yes" if value else "no"
