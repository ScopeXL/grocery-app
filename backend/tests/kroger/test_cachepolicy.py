"""What Kroger's cache headers let us keep (docs/PLAN.md §7.4, ADR 0016)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from dinnerbell.kroger.cachepolicy import cache_policy

NOW = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)


def headers(**values: str) -> httpx.Headers:
    return httpx.Headers({name.replace("_", "-"): value for name, value in values.items()})


def test_max_age_minus_age_sets_the_expiry() -> None:
    policy = cache_policy(headers(cache_control="public, max-age=3600", age="600"), NOW)
    assert policy.storable
    assert policy.expires_at == NOW + timedelta(seconds=3000)
    assert "max-age=3600" in policy.raw


def test_private_responses_are_still_ours_to_keep() -> None:
    policy = cache_policy(headers(cache_control="private, max-age=60"), NOW)
    assert policy.expires_at == NOW + timedelta(seconds=60)


@pytest.mark.parametrize(
    "control",
    ["no-store", "no-cache", "max-age=0", "public, no-store, max-age=600", "NO-STORE"],
)
def test_responses_that_forbid_or_end_caching_are_never_stored(control: str) -> None:
    assert not cache_policy(headers(cache_control=control), NOW).storable


def test_an_age_past_max_age_means_already_stale() -> None:
    assert not cache_policy(headers(cache_control="max-age=60", age="61"), NOW).storable


def test_expires_is_measured_against_the_servers_date() -> None:
    policy = cache_policy(
        headers(expires="Tue, 06 Oct 2026 15:00:00 GMT", date="Tue, 06 Oct 2026 14:30:00 GMT"),
        NOW,
    )
    assert policy.expires_at == NOW + timedelta(minutes=30)
    assert policy.raw.startswith("expires:")


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"expires": "0"},
        {"expires": "Tue, 06 Oct 2026 15:00:00 GMT"},  # no Date to measure against
        {"expires": "Tue, 06 Oct 2026 13:00:00 GMT", "date": "Tue, 06 Oct 2026 14:00:00 GMT"},
    ],
)
def test_without_usable_freshness_nothing_is_stored(values: dict[str, str]) -> None:
    assert not cache_policy(httpx.Headers(values), NOW).storable
