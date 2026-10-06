"""Kroger failures as plain-English API errors (docs/UX.md §6 "quiet states")."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dinnerbell.core.errors import envelope
from dinnerbell.kroger.client import (
    KrogerAuthError,
    KrogerDailyLimitError,
    KrogerError,
    KrogerRequestError,
)


def describe(exc: KrogerError, zone: ZoneInfo, now: datetime) -> tuple[int, dict[str, object]]:
    if isinstance(exc, KrogerDailyLimitError):
        when = about_time(exc.retry_at, zone, now)
        message = f"Store search is paused until about {when} — your list still works."
        return 503, envelope("kroger_daily_limit", message, retry_at=exc.retry_at.isoformat())
    if isinstance(exc, KrogerAuthError):
        message = "Store search isn't set up right. Ask whoever runs Dinner Bell to check it."
        return 503, envelope("kroger_setup", message)
    if isinstance(exc, KrogerRequestError):
        return 502, envelope("kroger_rejected", "Kroger couldn't handle that. Try other words.")
    message = "Kroger isn't answering right now. Try again in a minute."
    return 503, envelope("kroger_unavailable", message)


def about_time(moment: datetime, zone: ZoneInfo, now: datetime) -> str:
    """ "3:40 PM", "3:40 PM tomorrow" or "Tuesday 3:40 PM", in the household's time zone."""
    local = moment.astimezone(zone)
    clock = f"{local.hour % 12 or 12}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"
    today = now.astimezone(zone).date()
    if local.date() == today:
        return clock
    if local.date() == today + timedelta(days=1):
        return f"{clock} tomorrow"
    return f"{local.strftime('%A')} {clock}"


def install_kroger_error_handler(app: FastAPI, zone: ZoneInfo) -> None:
    @app.exception_handler(KrogerError)
    async def _kroger_error(request: Request, exc: KrogerError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        now = request.app.state.dinnerbell.clock.now()
        status, body = describe(exc, zone, now)
        return JSONResponse(body, status_code=status)
