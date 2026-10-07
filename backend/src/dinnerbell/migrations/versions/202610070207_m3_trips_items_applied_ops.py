"""m3: trips (saved lists), their items, and applied shopping ops

Revision ID: 202610070207
Revises: 202610070100
Create Date: 2026-10-07 02:07:00 UTC

Forward-only: never edit this file once it is listed in released.lock. Column types are plain
SQLAlchemy types on purpose: a released migration must not change when app code does.
(UTCDateTime is stored as DateTime; FractionText as String(32).)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202610070207"
down_revision: str | Sequence[str] | None = "202610070100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("store_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_ts", sa.BigInteger(), nullable=False),
        sa.Column("status_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("estimate_cents", sa.Integer(), nullable=False),
        sa.Column("savings_cents", sa.Integer(), nullable=False),
        sa.Column("not_priced", sa.Integer(), nullable=False),
        sa.Column("prices_as_of", sa.DateTime(), nullable=True),
        sa.Column("actual_total_cents", sa.Integer(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("product_cache_expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_member_id"],
            ["members.id"],
            name=op.f("fk_trips_created_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_trips_plan_id_plans"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["status_by_member_id"],
            ["members.id"],
            name=op.f("fk_trips_status_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name=op.f("fk_trips_store_id_stores"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trips")),
    )
    with op.batch_alter_table("trips") as batch:
        batch.create_index(batch.f("ix_trips_plan_id"), ["plan_id"], unique=False)
        batch.create_index(
            batch.f("ix_trips_product_cache_expires_at"), ["product_cache_expires_at"], unique=False
        )

    op.create_table(
        "applied_ops",
        sa.Column("op_id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("member_id", sa.String(length=36), nullable=True),
        sa.Column("client_ts", sa.BigInteger(), nullable=False),
        sa.Column("effective_ts", sa.BigInteger(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_applied_ops_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_applied_ops_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("op_id", name=op.f("pk_applied_ops")),
    )
    with op.batch_alter_table("applied_ops") as batch:
        batch.create_index(batch.f("ix_applied_ops_received_at"), ["received_at"], unique=False)
        batch.create_index(batch.f("ix_applied_ops_trip_id"), ["trip_id"], unique=False)

    op.create_table(
        "trip_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("line_key", sa.String(length=64), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("product_id", sa.String(length=16), nullable=True),
        sa.Column("upc", sa.String(length=16), nullable=True),
        sa.Column("image_url", sa.String(length=300), nullable=True),
        sa.Column("product_url", sa.String(length=300), nullable=True),
        sa.Column("size_text", sa.String(length=80), nullable=True),
        sa.Column("qty_text", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=8), nullable=False),
        sa.Column("unit_cents", sa.Integer(), nullable=True),
        sa.Column("line_cents", sa.Integer(), nullable=True),
        sa.Column("regular_cents", sa.Integer(), nullable=True),
        sa.Column("on_sale", sa.Boolean(), nullable=False),
        sa.Column("sale_ends", sa.Date(), nullable=True),
        sa.Column("section_key", sa.String(length=64), nullable=True),
        sa.Column("section_label", sa.String(length=120), nullable=True),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column("aisle_side", sa.String(length=1), nullable=True),
        sa.Column("bay", sa.Integer(), nullable=False),
        sa.Column("used_by", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.Column("state_ts", sa.BigInteger(), nullable=False),
        sa.Column("state_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("note_ts", sa.BigInteger(), nullable=False),
        sa.Column("note_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"], ["items.id"], name=op.f("fk_trip_items_item_id_items"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["note_by_member_id"],
            ["members.id"],
            name=op.f("fk_trip_items_note_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["state_by_member_id"],
            ["members.id"],
            name=op.f("fk_trip_items_state_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_trip_items_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_items")),
    )
    with op.batch_alter_table("trip_items") as batch:
        batch.create_index(batch.f("ix_trip_items_trip_id"), ["trip_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only; restore the pre-migration backup.")
