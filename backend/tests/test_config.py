from __future__ import annotations

import pytest

from dinnerbell.core.config import (
    PLACEHOLDER_SECRET,
    ConfigError,
    KrogerMode,
    load_settings,
)

GOOD = {
    "APP_BASE_URL": "https://dinner.example.test",
    "APP_SECRET_KEY": "a-very-long-random-secret-key-0123456789",
    "APP_PASSWORD": "correct horse battery",
    "TZ": "America/Chicago",
}


def problems(env: dict[str, str]) -> list[str]:
    with pytest.raises(ConfigError) as caught:
        load_settings(env)
    return caught.value.problems


def test_valid_settings_and_derived_values() -> None:
    settings = load_settings(GOOD | {"TRUSTED_PROXIES": "172.18.0.0/16, 10.0.0.2"})
    assert settings.is_https
    assert settings.cookie_name == "__Host-dinnerbell"
    assert settings.trusted_proxies == ("172.18.0.0/16", "10.0.0.2")
    assert settings.kroger_mode is KrogerMode.FAKE
    assert str(settings.db_path) == "/data/dinnerbell.db"
    assert settings.expected_redirect_uri == "https://dinner.example.test/api/kroger/callback"


def test_localhost_may_use_http_with_a_plain_cookie_name() -> None:
    settings = load_settings(GOOD | {"APP_BASE_URL": "http://localhost:5173"})
    assert not settings.is_https
    assert settings.cookie_name == "dinnerbell"


def test_problems_name_variables_but_never_echo_values() -> None:
    secret = "short-secret"
    found = problems({**GOOD, "APP_SECRET_KEY": secret, "APP_PASSWORD": "tiny", "TZ": "Mars/Base"})
    text = "\n".join(found)
    assert "APP_SECRET_KEY must be at least 32 characters" in text
    assert "APP_PASSWORD must be at least 12 characters" in text
    assert "TZ must be an IANA time zone" in text
    assert secret not in text
    assert "tiny" not in text


def test_missing_variables_are_listed_together() -> None:
    found = problems({})
    assert {"APP_BASE_URL is required", "APP_SECRET_KEY is required", "TZ is required"} <= set(
        found
    )


def test_placeholder_secret_is_rejected() -> None:
    found = problems({**GOOD, "APP_SECRET_KEY": PLACEHOLDER_SECRET})
    assert any("placeholder" in p for p in found)


@pytest.mark.parametrize(
    "url",
    ["http://dinner.example.test", "https://dinner.example.test/app", "ftp://x.test", "nonsense"],
)
def test_base_url_must_be_an_https_origin(url: str) -> None:
    assert any(p.startswith("APP_BASE_URL") for p in problems({**GOOD, "APP_BASE_URL": url}))


@pytest.mark.parametrize("proxies", ["*", "0.0.0.0/0", "::/0", "not-an-ip"])
def test_trusted_proxies_must_be_specific(proxies: str) -> None:
    assert any(
        p.startswith("TRUSTED_PROXIES") for p in problems({**GOOD, "TRUSTED_PROXIES": proxies})
    )


def test_live_kroger_needs_credentials() -> None:
    found = problems({**GOOD, "KROGER_MODE": "live"})
    assert any("KROGER_CLIENT_ID" in p for p in found)


def test_redirect_uri_must_match_base_url() -> None:
    found = problems({**GOOD, "KROGER_REDIRECT_URI": "https://other.example.test/callback"})
    assert any("KROGER_REDIRECT_URI" in p for p in found)


def test_test_mode_is_refused_off_localhost() -> None:
    found = problems({**GOOD, "DINNERBELL_TEST_MODE": "1"})
    assert any("DINNERBELL_TEST_MODE" in p for p in found)


def test_warnings_flag_typos_and_missing_proxy_list() -> None:
    settings = load_settings(GOOD)
    warnings = settings.warnings({"APP_PASSWROD": "x", "KROGER_SMOKE_ZIP": "x"})
    assert any("APP_PASSWROD" in w for w in warnings)
    assert not any("KROGER_SMOKE_ZIP" in w for w in warnings)
    assert any("TRUSTED_PROXIES" in w for w in warnings)


def test_secret_literals_cover_every_secret() -> None:
    settings = load_settings(
        GOOD | {"KROGER_MODE": "live", "KROGER_CLIENT_ID": "id", "KROGER_CLIENT_SECRET": "ksecret"}
    )
    assert set(settings.secret_literals()) == {
        GOOD["APP_SECRET_KEY"],
        GOOD["APP_PASSWORD"],
        "ksecret",
    }
