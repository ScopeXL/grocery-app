"""baseline: household, app_meta, members, devices

Revision ID: 202610061200
Revises:
Create Date: 2026-10-06 12:00:00 UTC

Forward-only: never edit this file once it is listed in released.lock.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202610061200"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "household",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("active_store_id", sa.String(length=36), nullable=True),
        sa.Column("default_cart_modality", sa.String(length=16), nullable=False),
        sa.Column("price_max_age_minutes", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_household_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_household")),
    )
    op.create_table(
        "app_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("auth_epoch", sa.Integer(), nullable=False),
        sa.Column("password_fp", sa.String(length=64), nullable=True),
        sa.Column("secret_key_check", sa.String(length=64), nullable=True),
        sa.Column("last_boot_version", sa.String(length=32), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_app_meta_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_meta")),
    )
    op.create_table(
        "members",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("marker_color", sa.String(length=16), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("member_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_devices_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
    )
    # The two single-row tables always exist.
    op.execute(
        "INSERT INTO household (id, name, active_store_id, default_cart_modality, "
        "price_max_age_minutes, updated_at) "
        "VALUES (1, 'Our household', NULL, 'PICKUP', 120, CURRENT_TIMESTAMP)"
    )
    op.execute("INSERT INTO app_meta (id, auth_epoch) VALUES (1, 1)")


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only; restore the pre-migration backup.")
