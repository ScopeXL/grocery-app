"""Household settings and members."""

from __future__ import annotations

from fastapi import APIRouter

from dinnerbell.auth.deps import SessionDep
from dinnerbell.household import service
from dinnerbell.household.models import Household
from dinnerbell.household.schemas import (
    MemberCreate,
    MemberOut,
    MemberUpdate,
    SettingsOut,
    SettingsUpdate,
)
from dinnerbell.state import StateDep

router = APIRouter(prefix="/api", tags=["household"])


def settings_out(home: Household) -> SettingsOut:
    modality = "DELIVERY" if home.default_cart_modality == "DELIVERY" else "PICKUP"
    return SettingsOut(household_name=home.name, cart_modality=modality)


@router.get("/settings")
async def get_settings(state: StateDep, session: SessionDep) -> SettingsOut:
    async with state.db.read() as db:
        return settings_out(await service.household(db))


@router.patch("/settings")
async def update_settings(
    body: SettingsUpdate, state: StateDep, session: SessionDep
) -> SettingsOut:
    async with state.db.write() as tx:
        home = await service.household(tx.session)
        if body.household_name is not None:
            home.name = body.household_name
        if body.cart_modality is not None:
            home.default_cart_modality = body.cart_modality
        tx.publish("settings.changed")
        return settings_out(home)


@router.get("/members")
async def list_members(state: StateDep, session: SessionDep) -> list[MemberOut]:
    async with state.db.read() as db:
        return [service.member_out(m) for m in await service.active_members(db)]


@router.post("/members", status_code=201)
async def create_member(body: MemberCreate, state: StateDep, session: SessionDep) -> MemberOut:
    async with state.db.write() as tx:
        member = await service.create_member(tx.session, body.name)
        tx.publish("members.changed", {"id": member.id})
        return service.member_out(member)


@router.patch("/members/{member_id}")
async def update_member(
    member_id: str, body: MemberUpdate, state: StateDep, session: SessionDep
) -> MemberOut:
    async with state.db.write() as tx:
        member = await service.get_member(tx.session, member_id)
        if body.name is not None:
            member.name = body.name
        if body.marker_color is not None:
            member.marker_color = body.marker_color
        tx.publish("members.changed", {"id": member.id})
        return service.member_out(member)


@router.post("/members/{member_id}/archive")
async def archive_member(member_id: str, state: StateDep, session: SessionDep) -> MemberOut:
    async with state.db.write() as tx:
        member = await service.archive_member(tx.session, member_id, state.clock.now())
        tx.publish("members.changed", {"id": member.id})
        return service.member_out(member)


@router.post("/members/{member_id}/restore")
async def restore_member(member_id: str, state: StateDep, session: SessionDep) -> MemberOut:
    async with state.db.write() as tx:
        member = await service.restore_member(tx.session, member_id)
        tx.publish("members.changed", {"id": member.id})
        return service.member_out(member)
