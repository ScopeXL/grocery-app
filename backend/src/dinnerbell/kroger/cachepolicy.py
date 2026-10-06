"""How long Kroger's cache headers let us keep a response (docs/PLAN.md §7.4, ADR 0016).

Kroger's terms forbid keeping copies longer than the cache headers permit. So a response with
`no-store`, `no-cache`, a zero lifetime or no freshness information at all is never stored.
`private` doesn't stop us: Dinner Bell is the household's own client, not a shared cache.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime


@dataclass(frozen=True, slots=True)
class CachePolicy:
    """`expires_at` is when a stored copy must be gone; None means "don't store it at all"."""

    expires_at: datetime | None
    raw: str = ""

    @property
    def storable(self) -> bool:
        return self.expires_at is not None


NOT_STORABLE = CachePolicy(expires_at=None)


def cache_policy(headers: Mapping[str, str], now: datetime) -> CachePolicy:
    """Read Cache-Control (max-age minus Age) or Expires (measured against Date)."""
    control = headers.get("cache-control", "").strip()
    expires = headers.get("expires", "").strip()
    raw = "; ".join(
        part
        for part in (control and f"cache-control: {control}", expires and f"expires: {expires}")
        if part
    )
    directives = _directives(control)
    if "no-store" in directives or "no-cache" in directives:
        return CachePolicy(None, raw)
    max_age = _seconds(directives.get("max-age"))
    if max_age is not None:
        remaining = max_age - (_seconds(headers.get("age")) or 0)
        return CachePolicy(now + timedelta(seconds=remaining) if remaining > 0 else None, raw)
    if expires:
        lifetime = _lifetime(expires, headers.get("date"))
        if lifetime is not None and lifetime > timedelta(0):
            return CachePolicy(now + lifetime, raw)
    return CachePolicy(None, raw)


def _directives(control: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for part in control.split(","):
        name, _, value = part.strip().partition("=")
        if name:
            found[name.strip().lower()] = value.strip().strip('"')
    return found


def _seconds(value: str | None) -> int | None:
    if value is None or not value.strip().isdigit():
        return None
    return int(value.strip())


def _lifetime(expires: str, date: str | None) -> timedelta | None:
    """Expires minus the server's Date, so clock skew between us and Kroger doesn't matter."""
    try:
        until = parsedate_to_datetime(expires)
        sent = parsedate_to_datetime(date) if date else None
    except TypeError, ValueError:
        return None  # "Expires: 0" and other junk mean "already expired"
    if until.tzinfo is None or (sent is not None and sent.tzinfo is None):
        return None
    if sent is None:
        return None  # without Date we can't tell how long Kroger meant; don't store
    return until - sent
