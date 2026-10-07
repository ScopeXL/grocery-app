"""Add a phone without the password (PLAN §10.2, UX §4.16): a signed-in phone shows a one-time
code, as a QR code and in letters, and the new phone scans it or types it.

* 8 characters from an alphabet without look-alikes (no 0, O, 1, I or L): about 40 bits.
  Wrong codes count against the login limits (5 tries per 15 minutes per address, 50 an hour
  in all), so nobody can guess one in its 10 minutes.
* Single-use, for 10 minutes: long enough to put the app on an iPhone's home screen first,
  where the home-screen app keeps its own sign-in (UX §5.1), and type the code there.
* Stored as an HMAC under its own key, so a copy of the database doesn't give away live codes.
* A new code retires the phone's older unused ones.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.auth.models import JoinCode
from dinnerbell.core.crypto import KeyPurpose, derive_key, mac

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LENGTH = 8
CODE_TTL = timedelta(minutes=10)


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def normalize(text: str) -> str | None:
    """What someone typed, as a code: any case, spaces and dashes ignored. None if it can't be."""
    code = "".join(text.split()).replace("-", "").upper()
    if len(code) != LENGTH or any(char not in ALPHABET for char in code):
        return None
    return code


def display(code: str) -> str:
    """ "4F7K 9QX2": two groups of four are easier to read out and type."""
    return f"{code[:4]} {code[4:]}"


def code_hash(secret: str, code: str) -> str:
    return mac(derive_key(secret, KeyPurpose.JOIN_CODE), code.encode()).hex()


async def prune(session: AsyncSession, now: datetime) -> None:
    """Used codes and expired ones have nothing left to do."""
    await session.execute(
        delete(JoinCode).where(or_(JoinCode.expires_at <= now, JoinCode.used_at.is_not(None)))
    )
