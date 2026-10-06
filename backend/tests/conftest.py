"""Shared fixtures.

* The real environment is stripped for every test, so a developer's .env can never leak in.
* The schema comes from the real migrations: a template database is migrated once per session
  and each test gets a copy (never ``create_all``).
"""

from __future__ import annotations

import os
import shutil
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from dinnerbell.app import create_app
from dinnerbell.core.clock import FakeClock
from dinnerbell.core.config import Settings
from dinnerbell.db import migrate
from tests.support import BASE_URL, ENV_NAMES, ENV_PREFIXES, make_settings


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        upper = key.upper()
        if upper.startswith(ENV_PREFIXES) or upper in ENV_NAMES:
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("template") / "dinnerbell.db"
    migrate.upgrade(path)
    return path


@pytest.fixture
def data_dir(tmp_path: Path, migrated_template: Path) -> Path:
    directory = tmp_path / "data"
    directory.mkdir()
    shutil.copy(migrated_template, directory / "dinnerbell.db")
    return directory


@pytest.fixture
def settings(data_dir: Path) -> Settings:
    return make_settings(data_dir)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 6, 14, 0, tzinfo=UTC))


@pytest.fixture
async def app(settings: Settings, clock: FakeClock) -> AsyncIterator[FastAPI]:
    application = create_app(settings, clock=clock, ping_interval_s=0.05)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http:
        yield http
