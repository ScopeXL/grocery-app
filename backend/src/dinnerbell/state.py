"""Everything the running app holds in memory, plus the FastAPI dependency that hands it out."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Request

from dinnerbell.auth.ratelimit import LoginLimiter
from dinnerbell.auth.sessions import AuthState, SessionCodec
from dinnerbell.core.clock import Clock
from dinnerbell.core.config import Settings
from dinnerbell.core.jobs import Jobs
from dinnerbell.db.backup import BackupService
from dinnerbell.db.engine import Database
from dinnerbell.events.hub import EventHub
from dinnerbell.kroger.account import KrogerAccount
from dinnerbell.kroger.catalog import ProductCatalog
from dinnerbell.kroger.client import KrogerApi


@dataclass
class AppState:
    settings: Settings
    clock: Clock
    db: Database
    hub: EventHub
    auth: AuthState
    codec: SessionCodec
    limiter: LoginLimiter
    backups: BackupService
    catalog: ProductCatalog
    kroger: KrogerApi
    account: KrogerAccount
    jobs: Jobs = field(default_factory=Jobs)
    # Items still to settle in each running send to the Kroger cart, by trip (shopping/cart.py)
    cart_sending: dict[str, set[str]] = field(default_factory=dict[str, set[str]])
    started: bool = False


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.dinnerbell
    return state


StateDep = Annotated[AppState, Depends(get_state)]
