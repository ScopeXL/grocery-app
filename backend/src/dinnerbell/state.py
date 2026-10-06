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
    jobs: Jobs = field(default_factory=Jobs)
    started: bool = False


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.dinnerbell
    return state


StateDep = Annotated[AppState, Depends(get_state)]
