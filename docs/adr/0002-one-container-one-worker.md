# ADR 0002: One container, one worker, SQLite in WAL mode

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The app serves one household of 2–6 people. It runs on the owner's Portainer host and must be easy to deploy for anyone who forks the public repo. Live updates need an in-process event hub. SQLite is the simplest durable store, and its backups are a single file.

## Decision

- **One image, one process.** `dinnerbell serve` runs uvicorn with `--workers 1` and serves the built SPA, the JSON API and SSE.
- **Storage:** SQLite at `/data/dinnerbell.db`, in WAL mode with `synchronous=NORMAL`, `foreign_keys=ON` and `busy_timeout=5000`, set on every connection. Writes are serialized by one `asyncio.Lock` and use `BEGIN IMMEDIATE`.
- **The single-worker invariant.** This is the only process serving the API. It holds the event hub, the write lock, SSE fan-out and the login rate limiter in memory.
  - Startup takes an exclusive `flock` on `/data/.lock`, so a second process or replica refuses to start.
  - CLAUDE.md states the invariant.

## Consequences

- **No cross-process coordination,** so no Redis and no queue. Live updates and rate limiting are simple and correct.
- **No horizontal scaling.** That's fine for one household. Running two workers would silently split live updates between phones, which is why it's prevented, not just documented.
- **`/data` must be a local filesystem.** NFS and CIFS break WAL's shared memory, so startup refuses them.
