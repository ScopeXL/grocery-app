"""Mains and Sides as the API sends them (docs/UX.md §4.6 to §4.8)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from dinnerbell.catalog.schemas import AmountIn, AmountOut, ItemOut

DishName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
RecipeUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^https?://\S+$")
]
Role = Literal["main", "side"]
Occasion = Literal["breakfast", "lunch", "dinner", "snack"]


class CostOut(BaseModel):
    """What the dish's own amounts cost at today's prices, as an estimate."""

    about_dollars: int | None  # "about $14"; None when nothing could be priced
    cents: int | None
    unpriced: int  # lines with no price: no product, no price, or an amount that won't convert


class DishCard(BaseModel):
    id: str
    name: str
    role: Role
    occasions: list[Occasion]
    favorite: bool
    photo_url: str | None  # the household's photo (thumbnail), cropped 4:3 on cards
    item_images: list[str]  # up to 3 product photos, shown uncropped when there's no photo
    cost: CostOut
    on_sale: bool  # something it uses is on sale at the store today
    sale_ends: date | None  # the earliest last day of those sales, when Kroger says
    archived: bool


class LineIn(BaseModel):
    item_id: str
    amount: AmountIn


class DishLineOut(BaseModel):
    id: str
    item: ItemOut
    amount: AmountOut
    share_text: str | None
    cost_cents: int | None
    check_amount: str | None  # why the amount needs a look, e.g. after a size was fixed


class DishOut(BaseModel):
    id: str
    name: str
    role: Role
    occasions: list[Occasion]
    servings: int | None
    notes: str | None
    recipe_url: str | None
    favorite: bool
    photo_id: str | None
    photo_url: str | None
    archived: bool
    lines: list[DishLineOut]
    cost: CostOut


class DishCreate(BaseModel):
    name: DishName
    role: Role
    occasions: list[Occasion] = Field(default_factory=lambda: ["dinner"], max_length=4)
    servings: Annotated[int, Field(ge=1, le=50)] | None = None
    notes: Notes | None = None
    recipe_url: RecipeUrl | None = None
    photo_id: str | None = None
    favorite: bool = False
    lines: list[LineIn] = Field(default_factory=list[LineIn], max_length=60)


class DishUpdate(BaseModel):
    """Only the fields sent change; send null to clear servings, notes, the link or the photo."""

    name: DishName | None = None
    role: Role | None = None
    occasions: list[Occasion] | None = Field(default=None, max_length=4)
    servings: Annotated[int, Field(ge=1, le=50)] | None = None
    notes: Notes | None = None
    recipe_url: RecipeUrl | None = None
    photo_id: str | None = None
    favorite: bool | None = None


class LinesIn(BaseModel):
    lines: list[LineIn] = Field(max_length=60)


class PhotoOut(BaseModel):
    id: str
    width: int
    height: int
