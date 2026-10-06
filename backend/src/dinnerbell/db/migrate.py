"""Running migrations safely at startup (docs/adr/0021-forward-only-migrations.md).

* ``foreign_keys=OFF`` is set when the connection opens. It is a no-op inside a transaction,
  and with it ON, Alembic's batch-mode table rebuild (DROP TABLE) would cascade deletes.
* Every pending migration runs inside ONE ``BEGIN IMMEDIATE`` transaction together with the
  ``alembic_version`` update, so a failure (or a SIGKILL) leaves the database exactly as it was.
* ``PRAGMA foreign_key_check`` must come back empty before commit.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool

from dinnerbell.db.engine import install_sqlite_hooks


class MigrationError(Exception):
    pass


class UnknownRevisionError(Exception):
    pass


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", "dinnerbell:migrations")
    return config


def script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(alembic_config())


def head_revision() -> str:
    heads = script_directory().get_heads()
    if len(heads) != 1:
        raise MigrationError(f"expected exactly one migration head, found {len(heads)}")
    return heads[0]


def known_revisions() -> set[str]:
    return {script.revision for script in script_directory().walk_revisions()}


def current_revision(db_path: Path) -> str | None:
    """The revision stamped in the database, or None for a new (or unmigrated) database."""
    if not db_path.exists():
        return None
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone()
        if not exists:
            return None
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return str(row[0]) if row else None
    finally:
        conn.close()


def migration_engine(db_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db_path}", poolclass=NullPool)
    install_sqlite_hooks(engine, immediate=True, foreign_keys=False)
    return engine


def check_known(db_path: Path) -> None:
    current = current_revision(db_path)
    if current is not None and current not in known_revisions():
        raise UnknownRevisionError(
            "The database was upgraded by a newer Dinner Bell. Redeploy that version, or "
            "restore the pre-upgrade backup (docs/RESTORE.md)."
        )


def is_pending(db_path: Path) -> bool:
    return current_revision(db_path) != head_revision()


def upgrade(db_path: Path) -> str:
    """Bring the database to head in one transaction. Returns the head revision."""
    target = head_revision()
    engine = migration_engine(db_path)
    try:
        with engine.connect() as conn, conn.begin():
            config = alembic_config()
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
            problems = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if problems:
                raise MigrationError(
                    f"foreign key check failed after migrating to {target} "
                    f"({len(problems)} problem rows)"
                )
    except MigrationError:
        raise
    except Exception as exc:
        raise MigrationError(f"migration to {target} failed: {type(exc).__name__}: {exc}") from exc
    finally:
        engine.dispose()
    return target


def verify(db_path: Path) -> None:
    """A fresh connection must see the head revision and pass quick_check."""
    target = head_revision()
    current = current_revision(db_path)
    if current != target:
        raise MigrationError(f"database is at {current}, expected {target}")
    conn = sqlite3.connect(db_path)
    try:
        result = conn.execute("PRAGMA quick_check").fetchone()
    finally:
        conn.close()
    if not result or result[0] != "ok":
        raise MigrationError("quick_check failed after migrating")
