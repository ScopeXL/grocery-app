"""Sign in, sign out, "Who's using this?", and signed-in devices."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.auth.deps import SessionDep, clear_session_cookie, set_session_cookie
from dinnerbell.auth.models import Device
from dinnerbell.auth.password import device_label, password_matches
from dinnerbell.auth.schemas import DeviceOut, LoginIn, MemberChoice, SessionOut
from dinnerbell.auth.sessions import SessionToken, day_number
from dinnerbell.core.errors import AppError
from dinnerbell.core.logging import get_logger
from dinnerbell.household import service as household_service
from dinnerbell.household.models import Member
from dinnerbell.state import AppState, StateDep

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = get_logger(__name__)


async def session_out(db: AsyncSession, device_id: str) -> SessionOut:
    device = await db.get(Device, device_id)
    members = await household_service.active_members(db)
    current = next((m for m in members if device and m.id == device.member_id), None)
    home = await household_service.household(db)
    return SessionOut(
        device_id=device_id,
        member=household_service.member_out(current) if current else None,
        members=[household_service.member_out(m) for m in members],
        household_name=home.name,
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response, state: StateDep) -> SessionOut:
    ip = _client_ip(request)
    wait = state.limiter.retry_after_seconds(ip)
    if wait is not None:
        minutes = max(1, round(wait / 60))
        raise AppError(
            429,
            "rate_limited",
            f"Too many tries. Wait {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )
    if not password_matches(body.password, state.settings.app_password):
        state.limiter.record_failure(ip)
        log.info("auth.login_failed")
        raise AppError(401, "wrong_password", "That password didn't match. Try again.")
    state.limiter.record_success(ip)
    now = state.clock.now()
    async with state.db.write() as tx:
        device = Device(label=device_label(request.headers.get("user-agent")), last_seen_at=now)
        tx.session.add(device)
        await tx.session.flush()
        state.auth.known_devices.add(device.id)
        state.auth.last_seen_written[device.id] = now
        token = SessionToken(device.id, state.auth.epoch, day_number(now))
        set_session_cookie(response, state.settings, state.codec.encode(token))
        log.info("auth.login", device=device.id)
        return await session_out(tx.session, device.id)


@router.get("/session")
async def get_session(state: StateDep, session: SessionDep) -> SessionOut:
    async with state.db.read() as db:
        return await session_out(db, session.device_id)


@router.put("/member")
async def choose_member(body: MemberChoice, state: StateDep, session: SessionDep) -> SessionOut:
    async with state.db.write() as tx:
        if body.member_id is not None:
            member = await tx.session.get(Member, body.member_id)
            if member is None or member.archived_at is not None:
                raise AppError(404, "not_found", "That person isn't in this household.")
        await tx.session.execute(
            update(Device).where(Device.id == session.device_id).values(member_id=body.member_id)
        )
        return await session_out(tx.session, session.device_id)


@router.post("/logout", status_code=204)
async def logout(response: Response, state: StateDep, session: SessionDep) -> None:
    await _revoke(state, [session.device_id])
    clear_session_cookie(response, state.settings)


@router.get("/devices")
async def list_devices(state: StateDep, session: SessionDep) -> list[DeviceOut]:
    async with state.db.read() as db:
        rows = await db.execute(
            select(Device, Member.name)
            .join(Member, Member.id == Device.member_id, isouter=True)
            .where(Device.revoked_at.is_(None))
            .order_by(Device.last_seen_at.desc())
        )
        return [
            DeviceOut(
                id=device.id,
                label=device.label,
                member_name=member_name,
                created_at=device.created_at,
                last_seen_at=device.last_seen_at,
                is_current=device.id == session.device_id,
            )
            for device, member_name in rows
        ]


@router.delete("/devices/{device_id}", status_code=204)
async def sign_out_device(
    device_id: str, response: Response, state: StateDep, session: SessionDep
) -> None:
    if device_id not in state.auth.known_devices:
        raise AppError(404, "not_found", "That device isn't signed in.")
    await _revoke(state, [device_id])
    if device_id == session.device_id:
        clear_session_cookie(response, state.settings)


@router.post("/devices/sign-out-others", status_code=204)
async def sign_out_others(state: StateDep, session: SessionDep) -> None:
    others = [d for d in state.auth.known_devices - state.auth.revoked_devices]
    await _revoke(state, [d for d in others if d != session.device_id])


async def _revoke(state: AppState, device_ids: list[str]) -> None:
    if not device_ids:
        return
    now = state.clock.now()
    async with state.db.write() as tx:
        await tx.session.execute(
            update(Device)
            .where(Device.id.in_(device_ids), Device.revoked_at.is_(None))
            .values(revoked_at=now)
        )
    state.auth.revoked_devices.update(device_ids)
    state.hub.drop_devices(set(device_ids))
    log.info("auth.devices_signed_out", count=len(device_ids))
