# Restoring a backup

Use this when the database is damaged, or to roll back after a release that changed the
database. Every step leaves the previous files in place, so you can always go back.

Backups live in the `dinnerbell_data` volume:
- `backups/dinnerbell.YYYY-MM-DD.db`: the nightly copies;
- `backups/pre-migrate/dinnerbell.<revision>.<time>.db`: the copy taken before each upgrade.

## 1. Pick the backup

On a computer with this repository, `just inspect-backup <file>` shows a backup's database
revision, app version and row counts.

On the server, do the same inside a throwaway container:

```bash
docker run --rm -v dinnerbell_data:/data --user 10001:10001 --entrypoint dinnerbell \
  scopexl/dinner-bell:latest inspect-backup /data/backups/dinnerbell.2026-10-06.db
```

## 2. Stop the stack

Portainer: **Stacks → dinner-bell → Stop this stack**.

## 3. Swap the files

Move the current database and its `-wal` and `-shm` files aside **together**. A stale `-wal`
next to a restored file corrupts it. Then copy the backup in:

```bash
docker run --rm -v dinnerbell_data:/data --user 10001:10001 --entrypoint sh \
  scopexl/dinner-bell:latest -c '
    cd /data && stamp=$(date +%Y%m%d%H%M%S) &&
    for f in dinnerbell.db dinnerbell.db-wal dinnerbell.db-shm; do
      [ -f "$f" ] && mv "$f" "dinnerbell.pre-restore.$stamp.${f#dinnerbell.}";
    done;
    cp backups/dinnerbell.2026-10-06.db dinnerbell.db'
```

## 4. Start the right version

Deploy an image **at or above** the backup's app version. The app runs any newer migrations
itself, after taking its own pre-upgrade copy. If you pick an image older than the backup's
database revision, it refuses to start (exit 65) instead of guessing.

## 5. Check

- `<your address>/api/version` shows the version you deployed.
- Sign in and spot-check the data.
- Keep the `dinnerbell.pre-restore.*` files for a week, then delete them.
