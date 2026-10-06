from __future__ import annotations

import logging

import pytest

from dinnerbell.core.logging import MASK, Redactor, configure_logging, get_logger

SECRET = "super-secret-value-123"


def test_sensitive_keys_are_masked() -> None:
    redact = Redactor()
    out = redact(
        None,
        "info",
        {"event": "x", "password": "p", "refresh_token": "r", "Cookie": "c", "code": "abc"},
    )
    assert out["password"] == out["refresh_token"] == out["Cookie"] == out["code"] == MASK


def test_literal_secrets_and_token_shapes_are_scrubbed_anywhere() -> None:
    redact = Redactor([SECRET])
    out = redact(
        None,
        "info",
        {
            "event": f"failed with {SECRET}",
            "detail": {"nested": ["Bearer abc.def-ghi", "gAAAAA" + "x" * 30]},
            "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl",
        },
    )
    assert SECRET not in str(out)
    assert "Bearer abc" not in str(out)
    assert "gAAAAA" not in str(out)
    assert "eyJhbGci" not in str(out)


def test_no_secret_reaches_captured_output(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json=True, secret_literals=[SECRET])
    get_logger("test").info("login.attempt", password=SECRET, note=f"value {SECRET}")
    logging.getLogger("uvicorn.error").info("stdlib message with %s", SECRET)
    captured = capsys.readouterr().out
    assert "login.attempt" in captured
    assert "stdlib message" in captured
    assert SECRET not in captured
