"""Health, version, diagnostics, backups and export."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text

from dinnerbell.auth.deps import SessionDep
from dinnerbell.core.errors import AppError
from dinnerbell.core.version import build_info
from dinnerbell.db import migrate
from dinnerbell.db.backup import NIGHTLY_RE
from dinnerbell.db.export import export_data
from dinnerbell.state import StateDep

router = APIRouter(prefix="/api", tags=["meta"])


class VersionOut(BaseModel):
    version: str
    revision: str
    created: str | None


class HealthOut(BaseModel):
    status: str


class LiveUpdatesInfo(BaseModel):
    connections: int
    epoch: str


class ClientInfo(BaseModel):
    resolved_ip: str | None
    scheme: str
    x_forwarded_for: str | None
    x_forwarded_proto: str | None
    trusted_proxies_configured: bool


class BackupFileOut(BaseModel):
    name: str
    bytes: int


class BackupStatusOut(BaseModel):
    directory: str
    schedule: str
    retention: str
    last_success_at: str | None
    last_error: str | None
    stale: bool
    files: list[BackupFileOut]


class BackupRunOut(BaseModel):
    file: str
    bytes: int
    seconds: float


class DiagnosticsOut(BaseModel):
    version: str
    revision: str
    schema_revision: str | None
    kroger_mode: str
    live_updates: LiveUpdatesInfo
    client: ClientInfo
    backups: BackupStatusOut


@router.get("/health", responses={503: {"model": HealthOut}})
async def health(state: StateDep, response: Response) -> HealthOut:
    if not state.started:
        response.status_code = 503
        return HealthOut(status="starting")
    try:
        async with state.db.read() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return HealthOut(status="database unavailable")
    return HealthOut(status="ok")


@router.get("/version")
async def version() -> VersionOut:
    info = build_info()
    return VersionOut(version=info.version, revision=info.revision, created=info.created)


@router.get("/admin/diagnostics")
async def diagnostics(request: Request, state: StateDep, session: SessionDep) -> DiagnosticsOut:
    info = build_info()
    headers = request.headers
    return DiagnosticsOut(
        version=info.version,
        revision=info.revision,
        schema_revision=migrate.current_revision(state.settings.db_path),
        kroger_mode=state.settings.kroger_mode.value,
        live_updates=LiveUpdatesInfo(connections=state.hub.connection_count, epoch=state.hub.epoch),
        client=ClientInfo(
            resolved_ip=request.client.host if request.client else None,
            scheme=request.url.scheme,
            x_forwarded_for=headers.get("x-forwarded-for"),
            x_forwarded_proto=headers.get("x-forwarded-proto"),
            trusted_proxies_configured=bool(state.settings.trusted_proxies),
        ),
        backups=BackupStatusOut.model_validate(state.backups.status()),
    )


@router.get("/admin/backups")
async def backups(state: StateDep, session: SessionDep) -> BackupStatusOut:
    return BackupStatusOut.model_validate(state.backups.status())


@router.post("/admin/backups/run")
async def run_backup(state: StateDep, session: SessionDep) -> BackupRunOut:
    try:
        result = await state.backups.run_now()
    except Exception as exc:
        raise AppError(500, "backup_failed", f"The backup didn't complete: {exc}") from exc
    return BackupRunOut(file=result.path.name, bytes=result.bytes, seconds=result.seconds)


@router.get("/admin/backups/{name}")
async def download_backup(name: str, state: StateDep, session: SessionDep) -> FileResponse:
    if not NIGHTLY_RE.match(name):
        raise AppError(404, "not_found", "That backup doesn't exist.")
    path = state.settings.backup_dir / name
    if not path.is_file():
        raise AppError(404, "not_found", "That backup doesn't exist.")
    return FileResponse(path, media_type="application/vnd.sqlite3", filename=name)


@router.get("/export")
async def export(state: StateDep, session: SessionDep) -> dict[str, Any]:
    async with state.db.read() as db:
        return await export_data(
            db,
            app_version=build_info().version,
            schema_revision=migrate.current_revision(state.settings.db_path),
            exported_at=state.clock.now(),
        )
