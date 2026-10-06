"""Factory for ``dinnerbell serve --reload`` (development only).

Each reloaded worker runs the same startup checks as production before creating the app.
"""

from __future__ import annotations

from fastapi import FastAPI

from dinnerbell.app import create_app
from dinnerbell.boot import prepare
from dinnerbell.core.clock import SystemClock
from dinnerbell.core.config import load_settings
from dinnerbell.core.logging import configure_logging


def create() -> FastAPI:
    settings = load_settings()
    configure_logging(settings.log_level, secret_literals=settings.secret_literals())
    prepare(settings, SystemClock())
    return create_app(settings)
