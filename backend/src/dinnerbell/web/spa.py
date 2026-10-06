"""Serving the built single-page app (docs/PLAN.md §4.1).

* ``/assets/*``: hashed build files, cached forever by the security-headers middleware; a
  missing asset is a 404, never index.html.
* top-level files (``sw.js``, ``manifest.webmanifest``, icons): served with ``no-cache``.
* every other GET outside /api: ``index.html`` with ``no-cache`` (client-side routing).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from dinnerbell.core.errors import AppError

mimetypes.add_type("application/manifest+json", ".webmanifest")
NO_CACHE = {"Cache-Control": "no-cache"}


def _not_found() -> AppError:
    return AppError(404, "not_found", "That couldn't be found.")


def mount_spa(app: FastAPI, static_dir: Path | None) -> None:
    if static_dir is None or not (static_dir / "index.html").is_file():

        @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
        async def no_frontend(path: str) -> Response:  # pyright: ignore[reportUnusedFunction]
            if path == "api" or path.startswith("api/"):
                raise _not_found()
            return PlainTextResponse(
                "The Dinner Bell API is running, but the frontend isn't built here. "
                "In development, open the Vite dev server instead.",
                status_code=404,
            )

        return

    root = static_dir.resolve()
    index = root / "index.html"
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa(path: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        if path == "api" or path.startswith("api/") or path.startswith("assets/"):
            raise _not_found()
        if path:
            candidate = (root / path).resolve()
            if candidate.is_file() and candidate.is_relative_to(root):
                return FileResponse(candidate, headers=NO_CACHE)
        return FileResponse(index, headers=NO_CACHE)
