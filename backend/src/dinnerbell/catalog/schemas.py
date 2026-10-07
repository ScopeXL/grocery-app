"""Items, product search results and the amount picker, as the API sends them.

Amounts travel as text ("3/8" or "0.375"); pydantic refuses JSON numbers for these fields, so
floats never reach the math (docs/PLAN.md §6, §8.1).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, StringConstraints


def _single_spaced(value: object) -> object:
    """Runs of spaces, tabs or line breaks inside a name become one space."""
    return " ".join(value.split()) if isinstance(value, str) else value


ItemName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    BeforeValidator(_single_spaced),
]
NumberText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=24)]
SizeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ProductId = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9A-Za-z]{1,16}$")]
AmountKindName = Literal["packages", "measure", "count"]


class AmountIn(BaseModel):
    kind: AmountKindName
    value: NumberText
    unit: str | None = None


class AmountOut(BaseModel):
    kind: AmountKindName
    value: str  # exact fraction text: "3/8"
    unit: str | None
    text: str  # how the screen shows it: "1/2 bag", "6 oz", "3"


class PriceOut(BaseModel):
    regular_cents: int
    sale_cents: int | None  # only while the sale is on
    sale_ends: date | None  # its last day, in the store's time zone
    per_pound: bool


class ProductResult(BaseModel):
    """A Kroger product, shown exactly as Kroger describes it. `product_id` links; never shown."""

    product_id: str
    description: str
    brand: str | None
    size: str | None
    image_url: str | None
    price: PriceOut | None
    availability: Literal["available", "low", "out", "not_sold"]
    sold_by: Literal["unit", "weight"]


class ItemOut(BaseModel):
    id: str
    name: str
    product_id: str | None
    image_url: str | None
    size_text: str | None  # the package size the math uses ("16 oz"), when it's known
    size_source: Literal["parsed", "household"]
    sold_by: Literal["unit", "weight"] | None
    each_weight_lb: str | None
    is_staple: bool
    archived: bool


class ItemCreate(BaseModel):
    name: ItemName
    product_id: ProductId | None = None


class ItemUpdate(BaseModel):
    """Only the fields sent change. `product_id: null` unlinks; `size_text: null` undoes a fix."""

    name: ItemName | None = None
    product_id: ProductId | None = None
    size_text: SizeText | None = None
    each_weight_lb: NumberText | None = None
    is_staple: bool | None = None


class KindOptionOut(BaseModel):
    kind: AmountKindName
    units: list[str]
    presets: list[AmountOut]
    step: str | None


class EachWeightOut(BaseModel):
    presets: list[str]  # pounds, as fraction text
    prefill: str | None


class PickerOut(BaseModel):
    """Everything the amount picker needs for one item (docs/UX.md §4.10)."""

    item: ItemOut
    product: ProductResult | None
    kinds: list[KindOptionOut]
    each_weight: EachWeightOut | None
    fix_size: bool


class PreviewIn(BaseModel):
    amount: AmountIn


class PreviewOut(BaseModel):
    valid: bool
    message: str | None  # why it can't be used, in plain English
    amount: AmountOut | None  # the amount as the server reads it, with its display text
    share_text: str | None  # "About half the 8 oz bag"
    cost_cents: int | None
