"""m5: the Kroger account link, Connect Kroger states, cart sends, and add-a-phone codes

Revision ID: 202610071347
Revises: 202610070207
Create Date: 2026-10-07 13:47:00 UTC

Forward-only: never edit this file once it is listed in released.lock. Column types are plain
SQLAlchemy types on purpose: a released migration must not change when app code does.
(UTCDateTime is stored as DateTime.)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202610071347"
down_revision: str | Sequence[str] | None = "202610070207"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kroger_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("access_enc", sa.Text(), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(), nullable=True),
        sa.Column("refresh_enc", sa.Text(), nullable=True),
        sa.Column("refresh_obtained_at", sa.DateTime(), nullable=True),
        sa.Column("scope", sa.String(length=200), nullable=True),
        sa.Column("connected_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_kroger_tokens_single_row")),
        sa.ForeignKeyConstraint(
            ["connected_by_member_id"],
            ["members.id"],
            name=op.f("fk_kroger_tokens_connected_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kroger_tokens")),
    )
    # Always present; empty until someone connects (PLAN §5).
    op.execute("INSERT INTO kroger_tokens (id, status, version) VALUES (1, 'disconnected', 0)")

    op.create_table(
        "kroger_oauth_states",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_kroger_oauth_states_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("state_hash", name=op.f("pk_kroger_oauth_states")),
    )
    with op.batch_alter_table("kroger_oauth_states") as batch:
        batch.create_index(
            batch.f("ix_kroger_oauth_states_device_id"), ["device_id"], unique=False
        )
        batch.create_index(
            batch.f("ix_kroger_oauth_states_expires_at"), ["expires_at"], unique=False
        )

    op.create_table(
        "cart_sends",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trip_id", sa.String(length=36), nullable=False),
        sa.Column("trip_item_id", sa.String(length=36), nullable=False),
        sa.Column("upc", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("modality", sa.String(length=16), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("sent_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["sent_by_member_id"],
            ["members.id"],
            name=op.f("fk_cart_sends_sent_by_member_id_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], name=op.f("fk_cart_sends_trip_id_trips"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["trip_item_id"],
            ["trip_items.id"],
            name=op.f("fk_cart_sends_trip_item_id_trip_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cart_sends")),
    )
    with op.batch_alter_table("cart_sends") as batch:
        batch.create_index(batch.f("ix_cart_sends_sent_at"), ["sent_at"], unique=False)
        batch.create_index(batch.f("ix_cart_sends_trip_id"), ["trip_id"], unique=False)
        batch.create_index(batch.f("ix_cart_sends_trip_item_id"), ["trip_item_id"], unique=False)

    op.create_table(
        "join_codes",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_device_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("used_by_device_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_device_id"],
            ["devices.id"],
            name=op.f("fk_join_codes_created_by_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["used_by_device_id"],
            ["devices.id"],
            name=op.f("fk_join_codes_used_by_device_id_devices"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("code_hash", name=op.f("pk_join_codes")),
    )
    with op.batch_alter_table("join_codes") as batch:
        batch.create_index(
            batch.f("ix_join_codes_created_by_device_id"), ["created_by_device_id"], unique=False
        )
        batch.create_index(batch.f("ix_join_codes_expires_at"), ["expires_at"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only; restore the pre-migration backup.")
