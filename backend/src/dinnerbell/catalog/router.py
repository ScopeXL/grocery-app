"""The household's items, and the amount picker's options and live preview."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from dinnerbell.auth.deps import SessionDep
from dinnerbell.catalog import service
from dinnerbell.catalog.models import Item
from dinnerbell.catalog.schemas import (
    ItemCreate,
    ItemOut,
    ItemUpdate,
    PickerOut,
    PreviewIn,
    PreviewOut,
)
from dinnerbell.core.errors import AppError
from dinnerbell.state import StateDep
from dinnerbell.stores.service import active_store

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("")
async def list_items(
    state: StateDep, session: SessionDep, q: Annotated[str | None, Query(max_length=80)] = None
) -> list[ItemOut]:
    async with state.db.read() as db:
        return [service.item_out(state, row) for row in await service.list_items(db, q)]


@router.post("", status_code=201)
async def create_item(body: ItemCreate, state: StateDep, session: SessionDep) -> ItemOut:
    product = await service.linked_product(state, body.product_id) if body.product_id else None
    async with state.db.write() as tx:
        row = Item(name=body.name)
        service.link(row, product)
        tx.session.add(row)
        await tx.session.flush()
        tx.publish("items.changed", {"id": row.id})
        return service.item_out(state, row)


@router.patch("/{item_id}")
async def update_item(
    item_id: str, body: ItemUpdate, state: StateDep, session: SessionDep
) -> ItemOut:
    sent = body.model_fields_set
    new_link = body.product_id if "product_id" in sent else None
    product = await service.linked_product(state, new_link) if new_link is not None else None
    undo_fix = "size_text" in sent and body.size_text is None
    async with state.db.read() as db:
        current = await service.get_item(db, item_id)
        store = await active_store(db)
    # Undoing a size fix goes back to Kroger's size, which needs the product (fetched first).
    original = await service.product_for(state, current, store) if undo_fix else None
    if undo_fix and current.product_id and original is None:
        raise AppError(
            503, "kroger_unavailable", "Kroger's size can't be fetched right now. Try again soon."
        )
    async with state.db.write() as tx:
        row = await service.get_item(tx.session, item_id)
        if body.name is not None:
            row.name = body.name
        if "product_id" in sent:
            service.link(row, product)
        if "size_text" in sent:
            if body.size_text is not None:
                service.fix_size(row, body.size_text)
            elif original is not None:
                service.link(row, original)
            else:
                row.size_text, row.size_source = None, "parsed"  # unlinked: nothing to go back to
        if "each_weight_lb" in sent:
            service.set_each_weight(row, body.each_weight_lb)
        if body.is_staple is not None:
            row.is_staple = body.is_staple
        tx.publish("items.changed", {"id": row.id})
        return service.item_out(state, row)


@router.post("/{item_id}/archive")
async def archive_item(item_id: str, state: StateDep, session: SessionDep) -> ItemOut:
    async with state.db.write() as tx:
        row = await service.get_item(tx.session, item_id)
        row.archived_at = state.clock.now()
        tx.publish("items.changed", {"id": row.id})
        return service.item_out(state, row)


@router.post("/{item_id}/restore")
async def restore_item(item_id: str, state: StateDep, session: SessionDep) -> ItemOut:
    async with state.db.write() as tx:
        row = await service.get_item(tx.session, item_id)
        row.archived_at = None
        tx.publish("items.changed", {"id": row.id})
        return service.item_out(state, row)


@router.get("/{item_id}/picker")
async def amount_picker(item_id: str, state: StateDep, session: SessionDep) -> PickerOut:
    return await service.picker(state, item_id)


@router.post("/{item_id}/preview")
async def preview_amount(
    item_id: str, body: PreviewIn, state: StateDep, session: SessionDep
) -> PreviewOut:
    return await service.preview(state, item_id, body.amount)
