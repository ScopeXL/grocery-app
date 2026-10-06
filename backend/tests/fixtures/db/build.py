"""Build a synthetic fixture database for a released migration revision (CLAUDE.md rule 4).

Every release adds `tests/fixtures/db/<revision>.sql`: the schema at that release plus a few
synthetic rows in every table. `tests/test_migrations.py` replays each file and migrates it to
head, so a new migration can't break a real household's data.

    cd backend && uv run python -m tests.fixtures.db.build 202610061200

Only synthetic values: "Sample Parent", location 99999001, made-up IDs.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

from alembic import command

from dinnerbell.db import migrate

HERE = Path(__file__).parent

# Synthetic rows to insert, per released revision (the tables that exist at that revision).
SEEDS: dict[str, list[str]] = {
    "202610061200": [
        "UPDATE household SET name = 'Sample household'",
        "UPDATE app_meta SET auth_epoch = 3, last_boot_version = '0.1.0'",
        "INSERT INTO members (id, name, marker_color, sort, created_at, archived_at) VALUES "
        "('00000000-0000-7000-8000-000000000001', 'Sample Parent', 'basil', 0, "
        "'2026-10-06 12:00:00', NULL), "
        "('00000000-0000-7000-8000-000000000002', 'Sample Kid', 'tomato', 1, "
        "'2026-10-06 12:01:00', NULL), "
        "('00000000-0000-7000-8000-000000000003', 'Sample Guest', 'plum', 2, "
        "'2026-10-06 12:02:00', '2026-10-06 13:00:00')",
        "INSERT INTO devices (id, label, member_id, created_at, last_seen_at, revoked_at) VALUES "
        "('00000000-0000-7000-8000-0000000000d1', 'iPhone', "
        "'00000000-0000-7000-8000-000000000001', '2026-10-06 12:00:00', "
        "'2026-10-06 12:30:00', NULL), "
        "('00000000-0000-7000-8000-0000000000d2', 'Android phone', NULL, "
        "'2026-10-06 12:05:00', '2026-10-06 12:06:00', '2026-10-06 12:40:00')",
    ],
}


def build(revision: str) -> Path:
    if revision not in SEEDS:
        raise SystemExit(f"add synthetic rows for {revision} to SEEDS first")
    out = HERE / f"{revision}.sql"
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "dinnerbell.db"
        engine = migrate.migration_engine(db)
        try:
            with engine.connect() as conn, conn.begin():
                config = migrate.alembic_config()
                config.attributes["connection"] = conn
                command.upgrade(config, revision)
                for statement in SEEDS[revision]:
                    conn.exec_driver_sql(statement)
        finally:
            engine.dispose()
        conn = sqlite3.connect(db)
        try:
            dump = "\n".join(conn.iterdump()) + "\n"
        finally:
            conn.close()
    out.write_text(dump)
    return out


if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(f"wrote {build(name).relative_to(Path.cwd())}")
