# ADR 0021: Forward-only migrations, run at startup after a backup

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The brief asks for three things on every startup:
- back up the database, then run migrations;
- if a migration fails, stop startup and leave the previous data untouched;
- never edit an applied migration.

The reference apps run migrations by hand and never test them; their tests use `create_all`, so drift between models and migrations is invisible.

There are also two SQLite traps:
- Alembic batch mode rebuilds tables, which cascades deletes if foreign keys are on.
- pysqlite doesn't wrap DDL in a transaction.

## Decision

**At startup** (PLAN §11.4)
1. A verified online backup goes into `/data/backups/pre-migrate/`, keeping the last 5. This only happens when migrations are pending or the app version changed.
2. Migrations run with `foreign_keys=OFF` set before `BEGIN IMMEDIATE`, inside one outer transaction, with `render_as_batch=True`.
3. `PRAGMA foreign_key_check` must come back empty.
4. Any error rolls back everything, including `alembic_version`, and the process exits with code 70.
5. If the database is at a revision this image doesn't know (a rollback after a newer migration), startup exits 65 and points to the restore guide.

**Forward-only.** `downgrade()` raises; rolling back means restoring the pre-migration backup.

**Released migrations are locked.**
- `released.lock` holds a sha256 for each released migration file.
- `just bump` appends to it.
- A test fails if a released file changes.

**Tests**
- Empty database → head, through the real boot path.
- `compare_metadata == []`.
- Every synthetic fixture database from a past release upgrades with row counts preserved.
- An injected failure rolls back.
- A batch rebuild keeps child rows that use `ON DELETE CASCADE`.

## Consequences

- A bad migration can't half-apply, and a good backup always exists before any schema change.
- Rolling back an image after a schema change needs a restore. The deploy report states whether a release changed the database.
- Each release that ships a migration must also commit a synthetic fixture database at the previous release's head.
