"""Migration safety (docs/adr/0021-forward-only-migrations.md)."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Integer, create_engine

from dinnerbell.db import migrate
from dinnerbell.db.models import Base

MIGRATIONS = Path(migrate.__file__).parent.parent / "migrations"


def test_empty_database_upgrades_to_a_single_head(tmp_path: Path) -> None:
    db = tmp_path / "dinnerbell.db"
    assert migrate.upgrade(db) == migrate.head_revision()
    migrate.verify(db)
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("SELECT count(*) FROM household").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM app_meta").fetchone()[0] == 1
    finally:
        conn.close()


def test_models_match_migrations(migrated_template: Path) -> None:
    engine = create_engine(f"sqlite:///{migrated_template}")
    with engine.connect() as conn:
        diff = compare_metadata(
            MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata
        )
    engine.dispose()
    assert diff == [], f"models and migrations differ: {diff}"


def test_released_migrations_are_unchanged() -> None:
    lock = (MIGRATIONS / "released.lock").read_text().splitlines()
    entries = [line.split() for line in lock if line.strip() and not line.startswith("#")]
    by_revision = {
        path.name.split("_", 1)[0]: path for path in (MIGRATIONS / "versions").glob("*.py")
    }
    for revision, digest in entries:
        path = by_revision.get(revision)
        assert path is not None, f"released migration {revision} is missing; never delete one"
        actual = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        assert actual == digest, f"released migration {revision} changed; write a new migration"


def test_a_failing_migration_leaves_the_database_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "dinnerbell.db"
    seed = sqlite3.connect(db)
    seed.execute("PRAGMA journal_mode=WAL")
    seed.execute("CREATE TABLE keepme (x INTEGER)")
    seed.execute("INSERT INTO keepme VALUES (1)")
    seed.commit()
    seed.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    seed.close()
    before = db.read_bytes()
    real_upgrade = migrate.command.upgrade

    def upgrade_then_fail(config: object, revision: str) -> None:
        real_upgrade(config, revision)  # pyright: ignore[reportArgumentType]
        raise RuntimeError("simulated failure after the DDL ran")

    monkeypatch.setattr(migrate.command, "upgrade", upgrade_then_fail)
    with pytest.raises(migrate.MigrationError):
        migrate.upgrade(db)
    assert migrate.current_revision(db) is None
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        rows = conn.execute("SELECT x FROM keepme").fetchall()
    finally:
        conn.close()
    assert tables == [("keepme",)]
    assert rows == [(1,)]
    assert db.read_bytes() == before


def test_batch_table_rebuild_keeps_child_rows(tmp_path: Path) -> None:
    """With foreign keys OFF (as at startup), rebuilding a parent table must not touch children."""
    db = tmp_path / "dinnerbell.db"
    migrate.upgrade(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO members (id, name, marker_color, sort, created_at) "
        "VALUES ('m1', 'Sample Parent', 'basil', 0, '2026-10-06 12:00:00')"
    )
    conn.execute(
        "INSERT INTO devices (id, label, member_id, created_at, last_seen_at) "
        "VALUES ('d1', 'Phone', 'm1', '2026-10-06 12:00:00', '2026-10-06 12:00:00')"
    )
    conn.commit()
    conn.close()

    engine = migrate.migration_engine(db)
    with engine.connect() as connection, connection.begin():
        operations = Operations(MigrationContext.configure(connection))
        with operations.batch_alter_table("members", recreate="always") as batch:
            batch.add_column(sa_column("temporary_flag"))
    engine.dispose()

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT member_id FROM devices WHERE id='d1'").fetchone()[0] == "m1"
    finally:
        conn.close()


def sa_column(name: str):
    from sqlalchemy import Column

    return Column(name, Integer, nullable=True)


def test_unknown_revision_is_detected(tmp_path: Path) -> None:
    db = tmp_path / "dinnerbell.db"
    migrate.upgrade(db)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE alembic_version SET version_num = '209912312359'")
    conn.commit()
    conn.close()
    with pytest.raises(migrate.UnknownRevisionError):
        migrate.check_known(db)
