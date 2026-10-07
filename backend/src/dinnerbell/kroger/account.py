"""The household's Kroger account: Connect Kroger, its tokens, and Disconnect (PLAN §7.5, §10.7).

* **Connect** stores a single-use state (hashed, 10 minutes) with a PKCE verifier and the
  device that asked, and hands back Kroger's sign-in URL. The callback marks the state used
  before anything else, then trades the code for tokens.
* **Tokens** are Fernet-encrypted under the `kroger-tokens-v1` key and never logged.
* **Refresh is single-flight:** one lock, the row re-read inside it, Kroger called outside any
  write transaction, and the new tokens written only if `version` hasn't moved since the read,
  so a Disconnect while a refresh is in flight wins. When Kroger sends no new refresh token,
  the old one is kept (`kroger.refresh_not_rotated`). Every refresh logs the refresh token's age,
  to settle how long Kroger's really last.
* **invalid_grant** means the link is gone: the tokens are wiped, the status becomes
  `needs_reconnect`, and every phone hears `settings.changed`. Any other failure keeps the
  tokens and backs off for a minute.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, cast

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import CursorResult, delete, update

from dinnerbell.auth.models import Device
from dinnerbell.core.clock import Clock
from dinnerbell.core.crypto import b64url
from dinnerbell.core.logging import get_logger
from dinnerbell.db.engine import Database
from dinnerbell.kroger.client import (
    KrogerApi,
    KrogerError,
    KrogerGrantError,
    KrogerUnavailableError,
    TokenGrant,
)
from dinnerbell.kroger.models import KrogerOAuthState, KrogerToken

log = get_logger(__name__)

STATE_TTL = timedelta(minutes=10)
# Refresh a little early, so a whole list of cart adds never runs out of token half-way.
ACCESS_MARGIN = timedelta(minutes=5)
REFRESH_BACKOFF = timedelta(minutes=1)


class AccountStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    NEEDS_RECONNECT = "needs_reconnect"


class ConnectResult(StrEnum):
    """How a callback ended; the phone is sent to `/settings?kroger=<result>`."""

    CONNECTED = "connected"
    DENIED = "denied"  # the person chose not to allow it on Kroger's page
    EXPIRED = "expired"  # unknown, used or older than 10 minutes
    FAILED = "failed"


class KrogerNotConnectedError(KrogerError):
    """There's no usable Kroger account: connect it (or reconnect it) in Settings."""

    def __init__(self, status: AccountStatus) -> None:
        super().__init__(f"The Kroger account is {status.value}")
        self.status = status


@dataclass(frozen=True, slots=True)
class Started:
    """A Connect in progress: where the phone goes to sign in to Kroger."""

    authorize_url: str


@dataclass(frozen=True, slots=True)
class _Snapshot:
    status: AccountStatus
    access_enc: str | None
    access_expires_at: datetime | None
    refresh_enc: str | None
    refresh_obtained_at: datetime | None
    version: int


def state_hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def code_challenge(verifier: str) -> str:
    """PKCE S256: base64url(sha256(verifier)), without padding (RFC 7636)."""
    return b64url(hashlib.sha256(verifier.encode()).digest())


def wiped(status: AccountStatus) -> dict[str, object]:
    """Column values for an account with no tokens."""
    return {
        "status": status.value,
        "access_enc": None,
        "access_expires_at": None,
        "refresh_enc": None,
        "refresh_obtained_at": None,
        "scope": None,
        "version": KrogerToken.version + 1,
    }


class KrogerAccount:
    def __init__(
        self,
        kroger: KrogerApi,
        db: Database,
        clock: Clock,
        cipher: Fernet,
        redirect_uri: str | None,
    ) -> None:
        self._kroger = kroger
        self._db = db
        self._clock = clock
        self._cipher = cipher
        self._redirect_uri = redirect_uri
        self._lock = asyncio.Lock()
        self._backoff_until: datetime | None = None

    @property
    def can_connect(self) -> bool:
        return self._redirect_uri is not None

    # ---- connecting -----------------------------------------------------------------------

    async def start(self, device_id: str) -> Started:
        if self._redirect_uri is None:
            raise RuntimeError("Connect Kroger needs KROGER_REDIRECT_URI")
        now = self._clock.now()
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)  # 86 characters, within PKCE's 43 to 128
        async with self._db.write() as tx:
            await tx.session.execute(
                delete(KrogerOAuthState).where(KrogerOAuthState.expires_at <= now)
            )
            tx.session.add(
                KrogerOAuthState(
                    state_hash=state_hash(state),
                    code_verifier=verifier,
                    device_id=device_id,
                    created_at=now,
                    expires_at=now + STATE_TTL,
                )
            )
        url = self._kroger.authorize_url(
            state=state, code_challenge=code_challenge(verifier), redirect_uri=self._redirect_uri
        )
        log.info("kroger.connect_started", device=device_id)
        return Started(authorize_url=url)

    async def claim(self, state: str) -> tuple[str, str] | None:
        """Mark the state used, first of all. Returns (code verifier, device that started it)."""
        now = self._clock.now()
        async with self._db.write() as tx:
            row = await tx.session.get(KrogerOAuthState, state_hash(state))
            if row is None or row.used_at is not None or row.expires_at <= now:
                return None
            row.used_at = now
            return row.code_verifier, row.device_id

    async def finish(self, code: str, verifier: str, device_id: str) -> ConnectResult:
        """Trade the callback's code for tokens and store them (the state is already claimed)."""
        assert self._redirect_uri is not None
        try:
            grant = await self._kroger.exchange_code(code, verifier, self._redirect_uri)
        except KrogerError as exc:
            log.warning("kroger.connect_failed", reason=type(exc).__name__)
            return ConnectResult.FAILED
        if grant.refresh_token is None:
            log.warning("kroger.connect_failed", reason="no_refresh_token")
            return ConnectResult.FAILED
        now = self._clock.now()
        async with self._db.write() as tx:
            device = await tx.session.get(Device, device_id)
            await tx.session.execute(
                update(KrogerToken)
                .where(KrogerToken.id == 1)
                .values(
                    status=AccountStatus.CONNECTED.value,
                    access_enc=self._encrypt(grant.access_token),
                    access_expires_at=now + grant.expires_in,
                    refresh_enc=self._encrypt(grant.refresh_token),
                    refresh_obtained_at=now,
                    scope=grant.scope,
                    connected_by_member_id=device.member_id if device else None,
                    connected_at=now,
                    version=KrogerToken.version + 1,
                )
            )
            tx.publish("settings.changed")
        log.info("kroger.connected", device=device_id)
        return ConnectResult.CONNECTED

    async def disconnect(self) -> None:
        """Forget the tokens and any Connect in progress. A refresh in flight can't undo this:
        its write needs the version it read."""
        async with self._db.write() as tx:
            await tx.session.execute(
                update(KrogerToken)
                .where(KrogerToken.id == 1)
                .values(
                    **wiped(AccountStatus.DISCONNECTED),
                    connected_by_member_id=None,
                    connected_at=None,
                )
            )
            await tx.session.execute(delete(KrogerOAuthState))
            tx.publish("settings.changed")
        self._backoff_until = None
        log.info("kroger.disconnected")

    # ---- using the account ----------------------------------------------------------------

    async def access_token(self) -> str:
        """A usable access token, refreshed first when it's nearly out.

        Raises KrogerNotConnectedError when there's no account (or it must be reconnected), and
        KrogerUnavailableError (or another KrogerError) when Kroger can't refresh it right now.
        """
        token = self._usable(await self._read())
        if token is not None:
            return token
        async with self._lock:
            snapshot = await self._read()  # another request may have refreshed it meanwhile
            token = self._usable(snapshot)
            if token is not None:
                return token
            return await self._refresh(snapshot)

    async def _refresh(self, snapshot: _Snapshot) -> str:
        if snapshot.status is not AccountStatus.CONNECTED or snapshot.refresh_enc is None:
            raise KrogerNotConnectedError(snapshot.status)
        now = self._clock.now()
        if self._backoff_until is not None and now < self._backoff_until:
            raise KrogerUnavailableError("Kroger couldn't refresh the account a moment ago")
        refresh_token = self._decrypt(snapshot.refresh_enc)
        if refresh_token is None:
            await self._lost(snapshot.version, reason="undecryptable")
            raise KrogerNotConnectedError(AccountStatus.NEEDS_RECONNECT)
        age_h = (
            round((now - snapshot.refresh_obtained_at).total_seconds() / 3600, 1)
            if snapshot.refresh_obtained_at
            else None
        )
        try:
            grant = await self._kroger.refresh(refresh_token)
        except KrogerGrantError:
            await self._lost(snapshot.version, reason="invalid_grant", token_age_h=age_h)
            raise KrogerNotConnectedError(AccountStatus.NEEDS_RECONNECT) from None
        except KrogerError as exc:
            self._backoff_until = now + REFRESH_BACKOFF
            log.warning("kroger.refresh_failed", reason=type(exc).__name__, token_age_h=age_h)
            raise
        self._backoff_until = None
        rotated = grant.refresh_token is not None
        log.info("kroger.refresh", token_age_h=age_h, rotated=rotated)
        if not rotated:
            log.info("kroger.refresh_not_rotated", token_age_h=age_h)
        if not await self._store_refresh(snapshot, grant, now):
            # Disconnected or reconnected while Kroger was answering: that change wins.
            latest = await self._read()
            token = self._usable(latest)
            if token is not None:
                return token
            if latest.status is AccountStatus.CONNECTED:
                raise KrogerUnavailableError("The Kroger account changed during a refresh")
            raise KrogerNotConnectedError(latest.status)
        return grant.access_token

    async def _store_refresh(self, snapshot: _Snapshot, grant: TokenGrant, now: datetime) -> bool:
        values: dict[str, object] = {
            "access_enc": self._encrypt(grant.access_token),
            "access_expires_at": now + grant.expires_in,
            "version": KrogerToken.version + 1,
        }
        if grant.refresh_token is not None:
            values["refresh_enc"] = self._encrypt(grant.refresh_token)
            values["refresh_obtained_at"] = now
        if grant.scope is not None:
            values["scope"] = grant.scope
        async with self._db.write() as tx:
            result = await tx.session.execute(
                update(KrogerToken)
                .where(KrogerToken.id == 1, KrogerToken.version == snapshot.version)
                .values(**values)
            )
            return cast(CursorResult[Any], result).rowcount > 0

    async def _lost(self, version: int, *, reason: str, token_age_h: float | None = None) -> None:
        """Kroger won't take the refresh token any more: ask the household to reconnect."""
        log.warning("kroger.needs_reconnect", reason=reason, token_age_h=token_age_h)
        async with self._db.write() as tx:
            result = await tx.session.execute(
                update(KrogerToken)
                .where(KrogerToken.id == 1, KrogerToken.version == version)
                .values(**wiped(AccountStatus.NEEDS_RECONNECT))
            )
            if cast(CursorResult[Any], result).rowcount > 0:
                tx.publish("settings.changed")

    # ---- helpers --------------------------------------------------------------------------

    async def _read(self) -> _Snapshot:
        async with self._db.read() as db:
            row = await db.get(KrogerToken, 1)
        if row is None:
            return _Snapshot(AccountStatus.DISCONNECTED, None, None, None, None, 0)
        return _Snapshot(
            status=AccountStatus(row.status),
            access_enc=row.access_enc,
            access_expires_at=row.access_expires_at,
            refresh_enc=row.refresh_enc,
            refresh_obtained_at=row.refresh_obtained_at,
            version=row.version,
        )

    def _usable(self, snapshot: _Snapshot) -> str | None:
        if snapshot.status is not AccountStatus.CONNECTED or snapshot.access_enc is None:
            return None
        expires = snapshot.access_expires_at
        if expires is None or expires - self._clock.now() <= ACCESS_MARGIN:
            return None
        return self._decrypt(snapshot.access_enc)

    def _encrypt(self, value: str) -> str:
        return self._cipher.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str | None:
        try:
            return self._cipher.decrypt(value.encode()).decode()
        except InvalidToken:
            return None  # written under another APP_SECRET_KEY
