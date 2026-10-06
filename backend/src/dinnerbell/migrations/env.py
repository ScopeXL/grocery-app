"""Alembic environment (docs/adr/0021-forward-only-migrations.md).

At startup, ``dinnerbell.db.migrate.upgrade`` passes in a connection that is already inside one
``BEGIN IMMEDIATE`` transaction; Alembic then adds no transactions of its own, so every
migration and the version stamp commit or roll back together.

From the command line (``just db-revision``), a connection to ``$DATA_DIR/dinnerbell.db`` is
made with the same pragmas. ``fileConfig()`` is deliberately never called: it would disable the
app's structlog loggers.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import context

from dinnerbell.db.migrate import migration_engine
from dinnerbell.db.models import Base

config = context.config
target_metadata = Base.metadata


def _run(connection: object) -> None:
    context.configure(
        connection=connection,  # pyright: ignore[reportArgumentType]
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    engine = migration_engine(data_dir / "dinnerbell.db")
    with engine.connect() as conn, conn.begin():
        _run(conn)
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL-script) migrations are not supported.")
run_migrations_online()
