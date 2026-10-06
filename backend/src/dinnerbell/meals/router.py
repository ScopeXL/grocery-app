"""Mains and Sides, and household photos."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from dinnerbell.auth.deps import SessionDep
from dinnerbell.core.errors import AppError
from dinnerbell.meals import photos, service
from dinnerbell.meals.models import Dish, Photo
from dinnerbell.meals.schemas import (
    DishCard,
    DishCreate,
    DishOut,
    DishUpdate,
    LinesIn,
    Occasion,
    PhotoOut,
    Role,
)
from dinnerbell.state import StateDep

router = APIRouter(prefix="/api", tags=["meals"])
PHOTO_CACHE = "private, max-age=31536000, immutable"  # a photo's bytes never change


@router.get("/dishes")
async def list_dishes(
    state: StateDep,
    session: SessionDep,
    role: Role | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    occasion: Occasion | None = None,
    favorite: bool | None = None,
    archived: bool = False,
) -> list[DishCard]:
    return await service.cards(
        state, role=role, query=q, occasion=occasion, favorite=favorite, archived=archived
    )


@router.post("/dishes", status_code=201)
async def create_dish(body: DishCreate, state: StateDep, session: SessionDep) -> DishOut:
    async with state.db.write() as tx:
        lines = await service.checked_lines(tx.session, body.lines)
        await service.check_photo(tx.session, body.photo_id)
        dish = Dish(
            name=body.name,
            role=body.role,
            occasions=list(dict.fromkeys(body.occasions)),
            servings=body.servings,
            notes=body.notes or None,
            recipe_url=body.recipe_url,
            photo_id=body.photo_id,
            favorite=body.favorite,
        )
        tx.session.add(dish)
        await tx.session.flush()
        service.write_lines(tx.session, dish, lines)
        tx.publish("dishes.changed", {"id": dish.id})
        dish_id = dish.id
    return await service.dish_out(state, dish_id)


@router.get("/dishes/{dish_id}")
async def get_dish(dish_id: str, state: StateDep, session: SessionDep) -> DishOut:
    return await service.dish_out(state, dish_id)


@router.patch("/dishes/{dish_id}")
async def update_dish(
    dish_id: str, body: DishUpdate, state: StateDep, session: SessionDep
) -> DishOut:
    sent = body.model_fields_set
    async with state.db.write() as tx:
        dish = await service.get_dish(tx.session, dish_id)
        if body.name is not None:
            dish.name = body.name
        if body.role is not None:
            dish.role = body.role
        if body.occasions is not None:
            dish.occasions = list(dict.fromkeys(body.occasions))
        if "servings" in sent:
            dish.servings = body.servings
        if "notes" in sent:
            dish.notes = body.notes or None
        if "recipe_url" in sent:
            dish.recipe_url = body.recipe_url
        if "photo_id" in sent:
            await service.check_photo(tx.session, body.photo_id)
            dish.photo_id = body.photo_id
        if body.favorite is not None:
            dish.favorite = body.favorite
        tx.publish("dishes.changed", {"id": dish.id})
    return await service.dish_out(state, dish_id)


@router.put("/dishes/{dish_id}/lines")
async def replace_lines(
    dish_id: str, body: LinesIn, state: StateDep, session: SessionDep
) -> DishOut:
    async with state.db.write() as tx:
        dish = await service.get_dish(tx.session, dish_id)
        lines = await service.checked_lines(tx.session, body.lines)
        await service.replace_lines(tx.session, dish, lines)
        tx.publish("dishes.changed", {"id": dish.id})
    return await service.dish_out(state, dish_id)


@router.post("/dishes/{dish_id}/duplicate", status_code=201)
async def duplicate_dish(dish_id: str, state: StateDep, session: SessionDep) -> DishOut:
    async with state.db.write() as tx:
        copy = await service.duplicate(tx.session, await service.get_dish(tx.session, dish_id))
        tx.publish("dishes.changed", {"id": copy.id})
        copy_id = copy.id
    return await service.dish_out(state, copy_id)


@router.post("/dishes/{dish_id}/archive")
async def archive_dish(dish_id: str, state: StateDep, session: SessionDep) -> DishOut:
    async with state.db.write() as tx:
        dish = await service.get_dish(tx.session, dish_id)
        dish.archived_at = state.clock.now()
        tx.publish("dishes.changed", {"id": dish.id})
    return await service.dish_out(state, dish_id)


@router.post("/dishes/{dish_id}/restore")
async def restore_dish(dish_id: str, state: StateDep, session: SessionDep) -> DishOut:
    async with state.db.write() as tx:
        dish = await service.get_dish(tx.session, dish_id)
        dish.archived_at = None
        tx.publish("dishes.changed", {"id": dish.id})
    return await service.dish_out(state, dish_id)


# ---- photos ---------------------------------------------------------------------------------


@router.post(
    "/photos",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"image/*": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload_photo(request: Request, state: StateDep, session: SessionDep) -> PhotoOut:
    """The raw image is the request body (JPEG, PNG, WebP…), up to 15 MB."""
    if not request.headers.get("content-type", "").startswith("image/"):
        raise AppError(415, "not_a_photo", "That file isn't a photo.")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > photos.MAX_UPLOAD_BYTES:
            raise AppError(413, "too_large", "That photo is too big. Try a smaller one.")
    encoded = await asyncio.to_thread(photos.encode, bytes(data))
    async with state.db.write() as tx:
        photo = Photo(
            webp=encoded.webp, thumb=encoded.thumb, width=encoded.width, height=encoded.height
        )
        tx.session.add(photo)
        await tx.session.flush()
        return PhotoOut(id=photo.id, width=photo.width, height=photo.height)


@router.get("/photos/{photo_id}", response_class=Response)
async def get_photo(photo_id: str, state: StateDep, session: SessionDep) -> Response:
    return await _photo(state, photo_id, thumb=False)


@router.get("/photos/{photo_id}/thumb", response_class=Response)
async def get_thumb(photo_id: str, state: StateDep, session: SessionDep) -> Response:
    return await _photo(state, photo_id, thumb=True)


async def _photo(state: StateDep, photo_id: str, *, thumb: bool) -> Response:
    async with state.db.read() as db:
        photo = await db.get(Photo, photo_id)
        if photo is None:
            raise AppError(404, "photo_not_found", "That photo couldn't be found.")
        body = photo.thumb if thumb else photo.webp
    return Response(body, media_type="image/webp", headers={"Cache-Control": PHOTO_CACHE})
