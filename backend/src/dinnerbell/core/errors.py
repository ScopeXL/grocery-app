"""One error envelope for the whole API: {"error": {"code": "...", "message": "..."}}.

Messages are plain English a household member can act on (docs/UX.md §2).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from dinnerbell.core.logging import get_logger

log = get_logger(__name__)

_STATUS_CODES: dict[int, tuple[str, str]] = {
    400: ("bad_request", "That request didn't make sense to the server."),
    401: ("signed_out", "Please sign in."),
    403: ("forbidden", "That isn't allowed."),
    404: ("not_found", "That couldn't be found."),
    405: ("method_not_allowed", "That action isn't supported here."),
    409: ("conflict", "Someone else just changed this. Refresh and try again."),
    413: ("too_large", "That's too much to send at once."),
    429: ("rate_limited", "Too many tries. Wait a little and try again."),
}


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers
        self.extra = extra or {}


def envelope(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, **extra}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse(
            envelope(exc.code, exc.message, **exc.extra),
            status_code=exc.status,
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        code, message = _STATUS_CODES.get(exc.status_code, ("error", "Something went wrong."))
        return JSONResponse(
            envelope(code, message),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        fields = sorted(
            {".".join(str(part) for part in error.get("loc", ())[1:]) for error in exc.errors()}
            - {""}
        )
        return JSONResponse(
            envelope("invalid", "Some of the details aren't valid.", fields=fields),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        log.exception("request.unhandled_error", path=request.url.path)
        return JSONResponse(
            envelope("server_error", "Something went wrong on the server. Try again."),
            status_code=500,
        )
