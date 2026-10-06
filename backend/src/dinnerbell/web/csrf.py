"""CSRF defence for the JSON API (docs/PLAN.md §10.3).

Every mutating /api request must carry ``X-Dinner-Bell: 1``. Other sites can't add that header
without CORS, which the app never grants. When an Origin header is present it must be the app's
own origin; ``Origin: null`` is rejected.
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from dinnerbell.core.errors import envelope

MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
HEADER = "x-dinner-bell"


class CSRFGuard:
    def __init__(self, app: ASGIApp, *, origin: str) -> None:
        self.app = app
        self.origin = origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] in MUTATING
            and str(scope["path"]).startswith("/api/")
        ):
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if headers.get(HEADER) != "1" or (origin is not None and origin != self.origin):
                response = JSONResponse(
                    envelope(
                        "csrf",
                        "This request was blocked for safety. Reload the page and try again.",
                    ),
                    status_code=403,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
