"""Security and caching headers on every response (docs/PLAN.md §10.5).

A pure ASGI middleware (not BaseHTTPMiddleware) so streaming responses (SSE) pass through
untouched.
"""

from __future__ import annotations

import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

KROGER_IMAGES = "https://www.kroger.com/product/images/"
_BASE_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    f"img-src 'self' data: blob: {KROGER_IMAGES}; font-src 'self'; "
    "{connect}; manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'; object-src 'none'"
)
PAGE_CSP = _BASE_CSP.format(connect="connect-src 'self'")
# The service worker pre-fetches a trip's product photos, so only its script may connect out.
SERVICE_WORKER_CSP = _BASE_CSP.format(connect="connect-src 'self' https://www.kroger.com")


class SecurityHeaders:
    def __init__(self, app: ASGIApp, *, https: bool) -> None:
        self.app = app
        self.https = https

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = (
                    SERVICE_WORKER_CSP if path == "/sw.js" else PAGE_CSP
                )
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "same-origin"
                headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                if self.https:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
                if path.startswith("/api/"):
                    if "cache-control" not in headers:
                        headers["Cache-Control"] = "no-store"
                    headers["X-Server-Time-Ms"] = str(int(time.time() * 1000))
                elif path.startswith("/assets/") and message["status"] == 200:
                    headers["Cache-Control"] = "public, max-age=31536000, immutable"
            await send(message)

        await self.app(scope, receive, send_with_headers)
