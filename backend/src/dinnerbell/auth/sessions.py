"""Per-device session cookies (docs/PLAN.md §10.2).

Cookie value: ``v1.<device_id>.<epoch>.<issued_day>.<mac>``. It is valid only when the MAC
verifies, the device exists and isn't revoked, and the epoch matches ``app_meta.auth_epoch``
(bumped when the password changes, which signs every device out).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from dinnerbell.core.crypto import KeyPurpose, b64url, constant_time_equal, derive_key, mac

VERSION = "v1"
MAX_AGE_SECONDS = 365 * 24 * 3600  # under Chrome's 400-day cap
REISSUE_AFTER_DAYS = 30


@dataclass(frozen=True, slots=True)
class SessionToken:
    device_id: str
    epoch: int
    issued_day: int


def day_number(moment: datetime) -> int:
    return int(moment.timestamp() // 86400)


class SessionCodec:
    def __init__(self, secret: str) -> None:
        self._key = derive_key(secret, KeyPurpose.SESSION)

    def _mac(self, body: str) -> str:
        return b64url(mac(self._key, body.encode())[:16])

    def encode(self, token: SessionToken) -> str:
        body = f"{VERSION}.{token.device_id}.{token.epoch}.{token.issued_day}"
        return f"{body}.{self._mac(body)}"

    def decode(self, value: str | None) -> SessionToken | None:
        if not value or len(value) > 200:
            return None
        parts = value.split(".")
        if len(parts) != 5 or parts[0] != VERSION:
            return None
        body = ".".join(parts[:4])
        if not constant_time_equal(parts[4], self._mac(body)):
            return None
        try:
            return SessionToken(device_id=parts[1], epoch=int(parts[2]), issued_day=int(parts[3]))
        except ValueError:
            return None


@dataclass
class AuthState:
    """In-memory mirror of what makes a session valid (single process, docs/adr/0002)."""

    epoch: int
    known_devices: set[str] = field(default_factory=set[str])
    revoked_devices: set[str] = field(default_factory=set[str])
    last_seen_written: dict[str, datetime] = field(default_factory=dict[str, datetime])

    def is_valid(self, token: SessionToken) -> bool:
        return (
            token.epoch == self.epoch
            and token.device_id in self.known_devices
            and token.device_id not in self.revoked_devices
        )
