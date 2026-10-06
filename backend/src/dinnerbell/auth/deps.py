"""The signed-in-device dependency used by every protected route."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy import update

from dinnerbell.auth.models import Device
from dinnerbell.auth.sessions import (
    MAX_AGE_SECONDS,
    REISSUE_AFTER_DAYS,
    SessionToken,
    day_number,
)
from dinnerbell.core.config import Settings
from dinnerbell.core.errors import AppError
from dinnerbell.state import AppState, StateDep

LAST_SEEN_EVERY = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class CurrentSession:
    device_id: str
    epoch: int


def set_session_cookie(response: Response, settings: Settings, value: str) -> None:
    response.set_cookie(
        settings.cookie_name,
        value,
        max_age=MAX_AGE_SECONDS,
        path="/",
        secure=settings.is_https,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.cookie_name, path="/", secure=settings.is_https, httponly=True, samesite="lax"
    )


def read_token(request: Request, state: AppState) -> SessionToken | None:
    token = state.codec.decode(request.cookies.get(state.settings.cookie_name))
    if token is None or not state.auth.is_valid(token):
        return None
    return token


async def current_session(request: Request, response: Response, state: StateDep) -> CurrentSession:
    token = read_token(request, state)
    if token is None:
        raise AppError(401, "signed_out", "Please sign in.")
    now = state.clock.now()
    today = day_number(now)
    if today - token.issued_day >= REISSUE_AFTER_DAYS:
        renewed = SessionToken(token.device_id, token.epoch, today)
        set_session_cookie(response, state.settings, state.codec.encode(renewed))
    last = state.auth.last_seen_written.get(token.device_id)
    if last is None or now - last >= LAST_SEEN_EVERY:
        state.auth.last_seen_written[token.device_id] = now
        async with state.db.write() as tx:
            await tx.session.execute(
                update(Device).where(Device.id == token.device_id).values(last_seen_at=now)
            )
    return CurrentSession(device_id=token.device_id, epoch=token.epoch)


SessionDep = Annotated[CurrentSession, Depends(current_session)]
