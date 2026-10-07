from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from dinnerbell.household.schemas import MemberOut


class LoginIn(BaseModel):
    password: Annotated[str, StringConstraints(max_length=256)]


class SessionOut(BaseModel):
    device_id: str
    member: MemberOut | None
    members: list[MemberOut]
    household_name: str


class MemberChoice(BaseModel):
    member_id: str | None


class DeviceOut(BaseModel):
    id: str
    label: str
    member_name: str | None
    created_at: datetime
    last_seen_at: datetime
    is_current: bool


class JoinCodeOut(BaseModel):
    code: str  # "4F7K9QX2", what the QR code carries
    display: str  # "4F7K 9QX2", for typing on the new phone
    url: str  # the QR code: the app's address + "/join#" + the code
    expires_at: datetime


class JoinIn(BaseModel):
    code: Annotated[str, StringConstraints(max_length=40)]
