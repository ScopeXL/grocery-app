"""m2: plans, planned meals and their sides, extras, item overrides, usual-side pairings

Revision ID: 202610070100
Revises: 202610062123
Create Date: 2026-10-07 01:00:00 UTC

Forward-only: never edit this file once it is listed in released.lock. Column types are plain
SQLAlchemy types on purpose: a released migration must not change when app code does.
(UTCDateTime is stored as DateTime; FractionText as String(32).)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202610070100"
down_revision: str | Sequence[str] | None = "202610062123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
    )
    op.create_table(
        "plan_extras",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=True),
        sa.Column("text", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("added_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "(item_id IS NULL) != (text IS NULL)", name=op.f("ck_plan_extras_item_or_text")
        ),
        sa.ForeignKeyConstraint(
            ["added_by_member_id"],
            ["members.id"],
            name=op.f("fk_plan_extras_added_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name=op.f("fk_plan_extras_item_id_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name=op.f("fk_plan_extras_plan_id_plans"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_extras")),
    )
    with op.batch_alter_table("plan_extras") as batch:
        batch.create_index(batch.f("ix_plan_extras_item_id"), ["item_id"], unique=False)
        batch.create_index(batch.f("ix_plan_extras_plan_id"), ["plan_id"], unique=False)

    op.create_table(
        "plan_item_overrides",
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("have_it", sa.Boolean(), nullable=True),
        sa.Column("qty_delta", sa.String(length=32), nullable=True),
        sa.Column("qty_delta_unit", sa.String(length=8), nullable=True),
        sa.Column("swap_product_id", sa.String(length=16), nullable=True),
        sa.Column("swap_upc", sa.String(length=16), nullable=True),
        sa.Column("swap_size_text", sa.String(length=80), nullable=True),
        sa.Column("swap_sold_by", sa.String(length=8), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name=op.f("fk_plan_item_overrides_item_id_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name=op.f("fk_plan_item_overrides_plan_id_plans"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("plan_id", "item_id", name=op.f("pk_plan_item_overrides")),
    )
    op.create_table(
        "dish_pairings",
        sa.Column("main_id", sa.String(length=36), nullable=False),
        sa.Column("side_id", sa.String(length=36), nullable=False),
        sa.Column("times_chosen", sa.Integer(), nullable=False),
        sa.Column("last_chosen_at", sa.DateTime(), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["main_id"],
            ["dishes.id"],
            name=op.f("fk_dish_pairings_main_id_dishes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["side_id"],
            ["dishes.id"],
            name=op.f("fk_dish_pairings_side_id_dishes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("main_id", "side_id", name=op.f("pk_dish_pairings")),
    )
    with op.batch_alter_table("dish_pairings") as batch:
        batch.create_index(batch.f("ix_dish_pairings_side_id"), ["side_id"], unique=False)

    op.create_table(
        "plan_meals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("main_id", sa.String(length=36), nullable=False),
        sa.Column("day", sa.Date(), nullable=True),
        sa.Column("occasion", sa.String(length=16), nullable=False),
        sa.Column("scale", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["added_by_member_id"],
            ["members.id"],
            name=op.f("fk_plan_meals_added_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["main_id"],
            ["dishes.id"],
            name=op.f("fk_plan_meals_main_id_dishes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name=op.f("fk_plan_meals_plan_id_plans"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_meals")),
    )
    with op.batch_alter_table("plan_meals") as batch:
        batch.create_index(batch.f("ix_plan_meals_main_id"), ["main_id"], unique=False)
        batch.create_index(batch.f("ix_plan_meals_plan_id"), ["plan_id"], unique=False)

    op.create_table(
        "plan_meal_sides",
        sa.Column("plan_meal_id", sa.String(length=36), nullable=False),
        sa.Column("side_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_meal_id"],
            ["plan_meals.id"],
            name=op.f("fk_plan_meal_sides_plan_meal_id_plan_meals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["side_id"],
            ["dishes.id"],
            name=op.f("fk_plan_meal_sides_side_id_dishes"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("plan_meal_id", "side_id", name=op.f("pk_plan_meal_sides")),
    )
    with op.batch_alter_table("plan_meal_sides") as batch:
        batch.create_index(batch.f("ix_plan_meal_sides_side_id"), ["side_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only; restore the pre-migration backup.")
