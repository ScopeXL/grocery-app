"""This week's plan and its shopping list as the API sends them (docs/UX.md §4.4, §4.5, §4.11).

Quantities travel as fraction text ("3/2"), with plain words beside them for the screen.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from dinnerbell.catalog.schemas import ProductResult
from dinnerbell.meals.schemas import Occasion

MAX_SIDES = 6

Scale = Literal["1/2", "1", "2"]
PurchaseUnitName = Literal["package", "each", "pound"]
ExtraText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Quantity = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16)]


class MemberRef(BaseModel):
    """Who added something, drawn in their marker color with their initial."""

    id: str
    name: str
    marker_color: str


class DishRef(BaseModel):
    id: str
    name: str
    photo_url: str | None  # the household's photo (thumbnail)
    item_images: list[str]  # up to 3 product photos, for a meal without a photo
    archived: bool


# ---- planned meals ----------------------------------------------------------------------------


class PlannedMealOut(BaseModel):
    id: str
    main: DishRef
    sides: list[DishRef]
    day: date | None  # a date in the household's time zone; None is "Any day"
    occasion: Occasion
    scale: Scale
    added_by: MemberRef | None


class MealCreate(BaseModel):
    main_id: str
    side_ids: list[str] = Field(default_factory=list[str], max_length=MAX_SIDES)
    day: date | None = None
    occasion: Occasion = "dinner"
    scale: Scale = "1"


class MealUpdate(BaseModel):
    """Only the fields sent change. Send `"day": null` for Any day."""

    main_id: str | None = None
    day: date | None = None
    occasion: Occasion | None = None
    scale: Scale | None = None


class SidesIn(BaseModel):
    side_ids: list[str] = Field(max_length=MAX_SIDES)


class UsualSideOut(BaseModel):
    id: str
    name: str
    photo_url: str | None
    pinned: bool  # the household chose it by hand, rather than it being learned


class UsualSidesIn(BaseModel):
    """The exact usual sides for a Main: listed ones are kept, any others are hidden."""

    side_ids: list[str] = Field(max_length=MAX_SIDES)


# ---- extras -----------------------------------------------------------------------------------


class ExtraCreate(BaseModel):
    """An item (from the household's items, or a product just turned into one) or plain text.

    `quantity` is in the item's list unit: packages, or pounds for things sold by weight.
    """

    item_id: str | None = None
    text: ExtraText | None = None
    quantity: Quantity = "1"
    note: Note | None = None

    @model_validator(mode="after")
    def _item_or_text(self) -> Self:
        if (self.item_id is None) == (self.text is None):
            raise ValueError("send either item_id or text")
        return self


class ExtraUpdate(BaseModel):
    quantity: Quantity | None = None
    note: Note | None = None


class ExtraOut(BaseModel):
    id: str
    item_id: str | None
    text: str | None
    name: str
    image_url: str | None
    quantity: str
    quantity_text: str  # "2 packages", "1 lb"
    note: str | None
    added_by: MemberRef | None
    line_key: str  # the list line it adds to


class UsualOut(BaseModel):
    """Something often added as an extra, offered as a one-tap re-add."""

    item_id: str | None
    text: str | None
    name: str
    image_url: str | None


# ---- the shopping list ------------------------------------------------------------------------


class UsedByOut(BaseModel):
    meal_id: str
    name: str  # the Main's name
    dish_names: list[str]  # the dishes in that meal that use the item, in line order


class LineExtraOut(BaseModel):
    id: str
    quantity: str
    added_by: MemberRef | None


class SaleOut(BaseModel):
    savings_cents: int
    ends: date | None  # the last day of the sale, in the store's time zone


class SectionOut(BaseModel):
    key: str  # "aisle:12", "cat:produce"
    label: str  # "Aisle 12, left side", "Produce"
    order: int  # the store's walking order


class LineOut(BaseModel):
    key: str  # the item's id, or "extra:<id>" for a plain-text extra
    item_id: str | None
    name: str
    image_url: str | None
    product_url: str | None  # "Open in Kroger"
    quantity: str  # what to buy, in `unit`
    quantity_text: str  # "2 boxes", "1 3/4 lb", "at least 1 package"
    amount_text: str  # with the size: "2 boxes, 16 oz each", "1 bag, 8 oz"
    unit: PurchaseUnitName
    computed: str  # what the plan alone asks for, before the household's change
    extra: str  # how much the extras add
    at_least: bool
    needed_text: str | None  # amounts that couldn't be converted: "6 oz needed"
    size_text: str | None  # one package: "16 oz"
    cost_cents: int | None
    regular_cents: int | None
    sale: SaleOut | None
    estimated_weight: bool  # priced from Kroger's estimate of one piece's weight ("est.")
    used_by: list[UsedByOut]
    extras: list[LineExtraOut]
    have_it: bool | None  # None: not asked yet (staples wait in the pantry check)
    staple: bool
    swapped: bool  # a different product, for this trip only
    warnings: list[str]  # plain English: "Not sold at your store", "Low stock", "No price"
    flags: list[str]
    section: SectionOut


class TotalsOut(BaseModel):
    total_cents: int
    savings_cents: int
    regular_total_cents: int
    not_priced: int  # lines without a full price ("3 items have no price")
    needs_check: int  # lines whose amount needs a second look after a swap
    have_it: int
    prices_as_of: datetime | None  # the oldest price used
    total_text: str  # "About $142"
    savings_text: str | None  # "$11 off on sale"
    prices_as_of_text: str | None  # "Prices as of 9:14 AM"
    not_priced_text: str | None  # "3 items have no price"


class PlanTripOut(BaseModel):
    """The plan's saved list while it's being shopped (UX §4.11's Start shopping)."""

    id: str
    item_count: int
    done_count: int  # checked off or couldn't find
    stale: bool  # the plan's list has changed since it was saved ("Update saved list")


class PlanOut(BaseModel):
    id: str | None  # None until something is planned
    today: date  # in the household's time zone, for Tonight and the day chips
    meals: list[PlannedMealOut]
    lines: list[LineOut]  # in the store's walking order
    extras: list[ExtraOut]
    usuals: list[UsualOut]
    totals: TotalsOut
    trip: PlanTripOut | None  # the saved list for this plan, if there is one
    prices_note: str | None  # why prices are missing right now, in plain English
    changed: str | None = None  # what this request added or changed (a meal, extra or plan id)


# ---- overrides and swaps ----------------------------------------------------------------------


class ItemOverrideIn(BaseModel):
    """Changes to one line for this plan. Only the fields sent change.

    * `have_it`: true "Have it", false "Need it", null back to "not asked".
    * `quantity` (with `unit`, the line's unit as shown): the final quantity wanted. The server
      keeps the difference from what the plan computes, so later meals still add on top.
      `"quantity": null` goes back to the computed quantity.
    * `swap_product_id`: buy this product instead, for this trip; null undoes the swap. With
      `always`, the item is linked to it for good instead.
    """

    have_it: bool | None = None
    quantity: Quantity | None = None
    unit: PurchaseUnitName | None = None
    swap_product_id: str | None = None
    always: bool = False


class NewWeekUndo(BaseModel):
    plan_id: str


class RepeatIn(BaseModel):
    """Plan these meals again: the meals planned with this saved list."""

    trip_id: str


class AlternativeOut(BaseModel):
    product: ProductResult
    unit_price_cents: str | None  # exact, per `unit_price_per`, for sorting
    unit_price_text: str | None  # "$0.25 per oz"
    current: bool  # the product the list uses now


class AlternativesOut(BaseModel):
    item_id: str
    alternatives: list[AlternativeOut]
