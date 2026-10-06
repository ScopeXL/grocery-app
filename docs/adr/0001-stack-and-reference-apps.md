# ADR 0001: Stack mirrors the owner's reference apps, with fixes

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The owner maintains two private FastAPI + React apps, which were reviewed as references for this project. The point of matching them is that the owner and future AI sessions already know the patterns.

What they share:
- **Backend:** uv (src layout, dependency groups), Python 3.12, FastAPI with a `create_app()` factory and lifespan, async SQLAlchemy 2.0 (typed `Mapped[]`) on aiosqlite, Alembic, pydantic-settings, structlog, httpx.
- **Backend checks:** pyright strict, ruff (`E,W,F,I,B,UP,N,RUF`), pytest in `asyncio_mode=auto` with `httpx.ASGITransport`.
- **Frontend:** pnpm, React 18, TypeScript (strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`), Vite, code-based TanStack Router, TanStack Query, Tailwind with semantic tokens and `cn()`.
- **Live updates:** SSE (broadcast bus → bounded queue per connection → heartbeat → reconnecting EventSource → debounced query invalidation).
- **Commands:** a justfile as the single command surface.

They also share these problems:
- No production build: the Vite dev server runs as "production".
- No Docker, CI, tags or CHANGELOG. The version is hard-coded in four places.
- Migrations are run by hand and never tested, because tests use `create_all`.
- SQLite pragmas are implicit, or applied offline.
- About 2,300 lines of hand-mirrored API types.
- `just check` covers the backend only. There is no frontend lint or test.
- A ~110 KB CLAUDE.md, loaded on every turn.
- Very large layered files (`models.py`, `schemas.py`).
- Tests can read the developer's real `.env`.
- No auth (they are LAN-only).

## Decision

Use the same stack and tools, at current versions (React 19, Vite 8, Tailwind 4, Python 3.14), and fix every problem above:

| Problem | Fix |
|---|---|
| No production build | Build the SPA into one Docker image and serve it from FastAPI |
| Migrations untested, run by hand | Run them at startup after a backup, and test them (ADR 0021) |
| Implicit pragmas | Explicit pragmas on every connection |
| Hand-mirrored API types | Generate them (ADR 0018) |
| Backend-only checks | One `just check` for both halves, also run in CI |
| Versioning and release | A single `VERSION` file, CHANGELOG and tags (ADR 0019) |
| Very large CLAUDE.md | Keep it at 15 KB or less, with detail in `docs/` |
| Large layered files | Feature packages |
| Tests read the real `.env` | An autouse fixture that isolates tests from the real environment |
| pyright strict in tests needs many ignores | Relax `reportPrivateUsage` for tests only |
| No auth | Real login and security headers (ADR 0004) |
| Hand-rolled background loops | One tiny job runner |

## Consequences

- Future sessions can reuse the reference apps' habits: test style, SSE plumbing, settings validation, backup design.
- The fixes cost some M0 time: CI, image pipeline, migration tests, API code generation. In return, every later milestone is safer.
- The reference apps are private, so this repo mentions them only generically and copies no values from them.
