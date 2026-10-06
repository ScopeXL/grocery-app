"""m1: stores, store sections, items, dishes, dish items, photos, Kroger cache and usage

Revision ID: 202610062123
Revises: 202610061200
Create Date: 2026-10-06 21:23:00 UTC

Forward-only: never edit this file once it is listed in released.lock. Column types are plain
SQLAlchemy types on purpose: a released migration must not change when app code does.
(UTCDateTime is stored as DateTime; FractionText as String(32).)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202610062123"
down_revision: str | Sequence[str] | None = "202610061200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("product_id", sa.String(length=16), nullable=True),
        sa.Column("upc", sa.String(length=16), nullable=True),
        sa.Column("size_text", sa.String(length=80), nullable=True),
        sa.Column("size_source", sa.String(length=16), nullable=False),
        sa.Column("sold_by", sa.String(length=8), nullable=True),
        sa.Column("each_weight_lb", sa.String(length=32), nullable=True),
        sa.Column("is_staple", sa.Boolean(), nullable=False),
        sa.Column("section_override_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_items")),
    )
    with op.batch_alter_table("items") as batch:
        batch.create_index(batch.f("ix_items_product_id"), ["product_id"], unique=False)

    op.create_table(
        "kroger_api_usage",
        sa.Column("api", sa.String(length=16), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=True),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
        sa.Column("last_429_at", sa.DateTime(), nullable=True),
        sa.Column("probe_backoff_s", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("api", name=op.f("pk_kroger_api_usage")),
    )
    op.create_table(
        "kroger_product_cache",
        sa.Column("product_id", sa.String(length=16), nullable=False),
        sa.Column("location_id", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("cache_control_raw", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("product_id", "location_id", name=op.f("pk_kroger_product_cache")),
    )
    with op.batch_alter_table("kroger_product_cache") as batch:
        batch.create_index(
            batch.f("ix_kroger_product_cache_expires_at"), ["expires_at"], unique=False
        )

    op.create_table(
        "photos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("webp", sa.LargeBinary(), nullable=False),
        sa.Column("thumb", sa.LargeBinary(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_photos")),
    )
    op.create_table(
        "stores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=16), nullable=False),
        sa.Column("chain", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("address_line1", sa.String(length=120), nullable=True),
        sa.Column("address_line2", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=True),
        sa.Column("zip_code", sa.String(length=16), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("chain_domain", sa.String(length=120), nullable=True),
        sa.Column("departments", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stores")),
        sa.UniqueConstraint("location_id", name=op.f("uq_stores_location_id")),
    )
    op.create_table(
        "dishes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=8), nullable=False),
        sa.Column("occasions", sa.JSON(), nullable=False),
        sa.Column("servings", sa.Integer(), nullable=True),
        sa.Column("photo_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recipe_url", sa.String(length=500), nullable=True),
        sa.Column("favorite", sa.Boolean(), nullable=False),
        sa.Column("last_planned_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["photo_id"],
            ["photos.id"],
            name=op.f("fk_dishes_photo_id_photos"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dishes")),
    )
    op.create_table(
        "store_sections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("sort_index", sa.Integer(), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=op.f("fk_store_sections_store_id_stores"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_sections")),
        sa.UniqueConstraint("store_id", "key", name=op.f("uq_store_sections_store_id")),
    )
    with op.batch_alter_table("store_sections") as batch:
        batch.create_index(batch.f("ix_store_sections_store_id"), ["store_id"], unique=False)

    op.create_table(
        "dish_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("amount_kind", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=8), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dish_id"],
            ["dishes.id"],
            name=op.f("fk_dish_items_dish_id_dishes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name=op.f("fk_dish_items_item_id_items"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dish_items")),
    )
    with op.batch_alter_table("dish_items") as batch:
        batch.create_index(batch.f("ix_dish_items_dish_id"), ["dish_id"], unique=False)
        batch.create_index(batch.f("ix_dish_items_item_id"), ["item_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only; restore the pre-migration backup.")
