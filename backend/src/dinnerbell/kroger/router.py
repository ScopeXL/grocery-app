"""Product search for the household's store, and the fake mode's placeholder photos."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from dinnerbell.auth.deps import SessionDep
from dinnerbell.catalog import service
from dinnerbell.catalog.schemas import ProductResult
from dinnerbell.core.errors import AppError
from dinnerbell.kroger.fake import image_svg
from dinnerbell.state import StateDep

router = APIRouter(prefix="/api/kroger", tags=["kroger"])
fake_images = APIRouter(prefix="/api/kroger", include_in_schema=False)


@router.get("/products")
async def search_products(
    state: StateDep, session: SessionDep, q: Annotated[str, Query(max_length=100)]
) -> list[ProductResult]:
    """Search terms are never stored or logged (ADR 0016)."""
    return await service.search_products(state, q)


@fake_images.get("/fake-images/{name}")
async def fake_image(name: str) -> Response:
    svg = image_svg(name)
    if svg is None:
        raise AppError(404, "not_found", "That photo couldn't be found.")
    return Response(
        svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )
