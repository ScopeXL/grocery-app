"""Key derivation and small crypto helpers (docs/PLAN.md §10.2, §10.7).

Every purpose gets its own HKDF subkey of APP_SECRET_KEY, so a key used for cookies can
never be confused with one used for encrypting Kroger tokens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from enum import StrEnum

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_SALT = b"dinnerbell-hkdf-v1"


class KeyPurpose(StrEnum):
    SESSION = "session-v1"
    KROGER_TOKENS = "kroger-tokens-v1"
    PASSWORD_FINGERPRINT = "password-fp-v1"  # noqa: S105 - a key label, not a password
    KEY_CHECK = "key-check-v1"


def derive_key(secret: str, purpose: KeyPurpose) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=purpose.value.encode())
    return hkdf.derive(secret.encode())


def mac(key: bytes, message: bytes) -> bytes:
    return hmac.new(key, message, hashlib.sha256).digest()


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def password_fingerprint(secret: str, password: str) -> str:
    """Detects a changed APP_PASSWORD across restarts without storing the password."""
    return mac(derive_key(secret, KeyPurpose.PASSWORD_FINGERPRINT), password.encode()).hex()


def key_check(secret: str) -> str:
    """Detects a changed APP_SECRET_KEY across restarts."""
    return mac(derive_key(secret, KeyPurpose.KEY_CHECK), b"dinnerbell key check").hex()[:32]


def token_cipher(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(derive_key(secret, KeyPurpose.KROGER_TOKENS)))
