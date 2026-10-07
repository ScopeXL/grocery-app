"""The FastAPI application factory."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dinnerbell.auth import join as auth_join
from dinnerbell.auth.models import Device
from dinnerbell.auth.ratelimit import LoginLimiter
from dinnerbell.auth.router import router as auth_router
from dinnerbell.auth.sessions import AuthState, SessionCodec
from dinnerbell.catalog.router import router as items_router
from dinnerbell.core.clock import Clock, SystemClock
from dinnerbell.core.config import KrogerMode, Settings
from dinnerbell.core.crypto import token_cipher
from dinnerbell.core.errors import install_error_handlers
from dinnerbell.core.logging import get_logger
from dinnerbell.core.version import build_info
from dinnerbell.db.backup import BackupService
from dinnerbell.db.engine import Database, make_database
from dinnerbell.events.hub import EventHub
from dinnerbell.events.router import router as events_router
from dinnerbell.household.models import AppMeta
from dinnerbell.household.router import router as household_router
from dinnerbell.kroger import account as kroger_account
from dinnerbell.kroger.account import KrogerAccount
from dinnerbell.kroger.catalog import ProductCatalog
from dinnerbell.kroger.client import KrogerApi
from dinnerbell.kroger.dbusage import DbUsageStore
from dinnerbell.kroger.errors import install_kroger_error_handler
from dinnerbell.kroger.fake import FakeKroger
from dinnerbell.kroger.live import LiveKroger
from dinnerbell.kroger.router import fake_routes as kroger_fake_routes
from dinnerbell.kroger.router import router as kroger_router
from dinnerbell.kroger.usage import UsageGuard
from dinnerbell.meals import service as meals_service
from dinnerbell.meals.router import router as meals_router
from dinnerbell.meta.router import router as meta_router
from dinnerbell.meta.testing import router as testing_router
from dinnerbell.planning.router import router as planning_router
from dinnerbell.shopping import cart as shopping_cart
from dinnerbell.shopping import service as shopping_service
from dinnerbell.shopping.router import router as shopping_router
from dinnerbell.state import AppState
from dinnerbell.stores.router import router as stores_router
from dinnerbell.web.csrf import CSRFGuard
from dinnerbell.web.headers import SecurityHeaders
from dinnerbell.web.spa import mount_spa

log = get_logger(__name__)
BACKUP_CHECK_INTERVAL_S = 600
CACHE_PURGE_INTERVAL_S = 3600
PHOTO_PURGE_INTERVAL_S = 6 * 3600


def make_kroger(settings: Settings, db: Database, clock: Clock) -> KrogerApi:
    if settings.kroger_mode is KrogerMode.FAKE:
        return FakeKroger(clock)
    assert settings.kroger_client_id and settings.kroger_client_secret  # checked by Settings
    return LiveKroger(
        settings.kroger_client_id.get_secret_value(),
        settings.kroger_client_secret.get_secret_value(),
        usage=UsageGuard(DbUsageStore(db), clock),
        clock=clock,
    )


def redirect_uri(settings: Settings) -> str | None:
    """Where Kroger sends a phone back after Connect Kroger. Live mode needs it set (and
    registered on the Kroger app); the demo sign-in always comes back to this server."""
    if settings.kroger_mode is KrogerMode.FAKE:
        return settings.kroger_redirect_uri or settings.expected_redirect_uri
    return settings.kroger_redirect_uri


async def load_auth_state(db: Database) -> AuthState:
    async with db.read() as session:
        meta = await session.get(AppMeta, 1)
        rows = (await session.execute(select(Device.id, Device.revoked_at))).all()
    return AuthState(
        epoch=meta.auth_epoch if meta else 1,
        known_devices={device_id for device_id, _ in rows},
        revoked_devices={device_id for device_id, revoked in rows if revoked is not None},
    )


class RequestLog:
    """Logs method, path (never the query string), status and duration."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/api/health":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            if str(scope["path"]).startswith("/api/"):
                log.info(
                    "http.request",
                    method=scope["method"],
                    path=scope["path"],
                    status=status,
                    ms=round((time.perf_counter() - started) * 1000, 1),
                )


def create_app(
    settings: Settings, *, clock: Clock | None = None, ping_interval_s: float = 15.0
) -> FastAPI:
    the_clock = clock or SystemClock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        db = make_database(settings.db_path)
        hub = EventHub(ping_interval_s=ping_interval_s)
        db.publisher = hub.publish
        kroger = make_kroger(settings, db, the_clock)
        catalog = ProductCatalog(kroger, db, the_clock)
        account = KrogerAccount(
            kroger,
            db,
            the_clock,
            token_cipher(settings.app_secret_key.get_secret_value()),
            redirect_uri(settings),
        )
        state = AppState(
            settings=settings,
            clock=the_clock,
            db=db,
            hub=hub,
            auth=await load_auth_state(db),
            codec=SessionCodec(settings.app_secret_key.get_secret_value()),
            limiter=LoginLimiter(the_clock),
            backups=BackupService(
                db_path=settings.db_path,
                backup_dir=settings.backup_dir,
                zone=settings.zone,
                clock=the_clock,
            ),
            catalog=catalog,
            kroger=kroger,
            account=account,
        )

        async def purge_kroger_cache() -> None:
            await catalog.purge_expired()

        async def purge_orphan_photos() -> None:
            async with db.write() as tx:
                await meals_service.purge_orphan_photos(tx.session, the_clock.now())

        state.jobs.every("nightly-backup", BACKUP_CHECK_INTERVAL_S, state.backups.tick)
        state.jobs.every("kroger-cache-purge", CACHE_PURGE_INTERVAL_S, purge_kroger_cache)

        async def tidy_trips() -> None:
            async with db.write() as tx:
                now = the_clock.now()
                await shopping_service.clear_kroger_copies(tx.session, now)
                await shopping_service.prune_ops(tx.session, now)
                await shopping_cart.prune(tx.session, now)
                await kroger_account.prune_states(tx.session, now)
                await auth_join.prune(tx.session, now)

        state.jobs.every("orphan-photos", PHOTO_PURGE_INTERVAL_S, purge_orphan_photos)
        state.jobs.every("tidy-trips", CACHE_PURGE_INTERVAL_S, tidy_trips)
        app.state.dinnerbell = state
        state.started = True
        log.info("app.started", version=build_info().version, revision=build_info().revision)
        try:
            yield
        finally:
            state.started = False
            hub.close()
            await state.jobs.stop()
            await kroger.aclose()
            await db.dispose()
            log.info("app.stopped")

    app = FastAPI(
        title="Dinner Bell",
        version="0",
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    install_error_handlers(app)
    install_kroger_error_handler(app, settings.zone)
    app.include_router(meta_router)
    app.include_router(auth_router)
    app.include_router(household_router)
    app.include_router(stores_router)
    app.include_router(kroger_router)
    if settings.kroger_mode is KrogerMode.FAKE:
        app.include_router(kroger_fake_routes)
    app.include_router(items_router)
    app.include_router(meals_router)
    app.include_router(planning_router)
    app.include_router(shopping_router)
    app.include_router(events_router)
    if settings.dinnerbell_test_mode:
        app.include_router(testing_router)
    mount_spa(app, settings.dinnerbell_static_dir)
    app.add_middleware(CSRFGuard, origin=settings.app_base_url)
    app.add_middleware(SecurityHeaders, https=settings.is_https)
    app.add_middleware(RequestLog)
    return app
