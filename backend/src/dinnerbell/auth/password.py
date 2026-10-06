"""The household password check (docs/adr/0004-household-password-login.md)."""

from __future__ import annotations

import hashlib
import hmac

from pydantic import SecretStr


def password_matches(given: str, configured: SecretStr) -> bool:
    """Constant-time comparison of SHA-256 digests (equal length, no early exit)."""
    given_digest = hashlib.sha256(given.encode()).digest()
    configured_digest = hashlib.sha256(configured.get_secret_value().encode()).digest()
    return hmac.compare_digest(given_digest, configured_digest)


def device_label(user_agent: str | None) -> str:
    """A short, human label for the Devices list ("iPhone, Safari")."""
    ua = user_agent or ""
    if "iPhone" in ua:
        device = "iPhone"
    elif "iPad" in ua:
        device = "iPad"
    elif "Android" in ua:
        device = "Android phone" if "Mobile" in ua else "Android tablet"
    elif "Macintosh" in ua:
        device = "Mac"
    elif "Windows" in ua:
        device = "Windows PC"
    elif "Linux" in ua:
        device = "Linux computer"
    else:
        device = "Device"
    if "Edg/" in ua:
        browser = "Edge"
    elif "Firefox/" in ua or "FxiOS" in ua:
        browser = "Firefox"
    elif "Chrome/" in ua or "CriOS" in ua:
        browser = "Chrome"
    elif "Safari/" in ua:
        browser = "Safari"
    else:
        return device
    return f"{device}, {browser}"
