from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

ZipCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{5}$")]
LocationId = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9A-Za-z]{1,16}$")
]


class StoreOption(BaseModel):
    """A store found near a ZIP code. `location_id` picks it; the screen never shows it."""

    location_id: str
    name: str
    address_lines: list[str]


class StoreOut(BaseModel):
    name: str
    address_lines: list[str]


class ActiveStoreOut(BaseModel):
    store: StoreOut | None


class ChooseStore(BaseModel):
    location_id: LocationId


class StoreSectionOut(BaseModel):
    """One stop on the walk through the store (`aisle:12`, `cat:produce`)."""

    id: str
    key: str
    label: str


class SectionOrderIn(BaseModel):
    """Every section of the store, in the order the household walks it."""

    ids: list[str] = Field(max_length=500)
