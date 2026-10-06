from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

MemberName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
HouseholdName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
MarkerColor = Literal["basil", "tomato", "carrot", "eggplant", "beet", "olive", "cocoa", "plum"]


class MemberOut(BaseModel):
    id: str
    name: str
    marker_color: MarkerColor


class MemberCreate(BaseModel):
    name: MemberName


class MemberUpdate(BaseModel):
    name: MemberName | None = None
    marker_color: MarkerColor | None = None


class SettingsOut(BaseModel):
    household_name: str


class SettingsUpdate(BaseModel):
    household_name: HouseholdName | None = None
