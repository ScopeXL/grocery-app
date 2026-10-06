# ADR 0018: Frontend API types are generated from the backend's OpenAPI schema

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The reference apps hand-mirror their API types: 2,300 lines in one of them, kept in sync "manually for now". That drift risk is exactly what an AI-maintained repo must not carry.

## Decision

1. `dinnerbell openapi` dumps the FastAPI schema with sorted keys, and `info.version` pinned to `"0"` so version bumps don't change the output. It goes to `frontend/src/api/openapi.json`.
2. `openapi-typescript` turns that into `frontend/src/api/schema.d.ts`.
3. The frontend calls the API through `openapi-fetch`, wrapped in `client.ts`. The wrapper adds the CSRF header, clock sampling and the error envelope.
4. Both generated files are committed.
5. `just api-types-check` regenerates them into a temporary directory and diffs. It's part of `just check`, so CI fails when they're stale.

## Consequences

- Backend schema changes show up as type errors in the frontend straight away.
- Pydantic response models must be precise, which is good practice anyway: every route has a return type annotation, and there are no untyped dicts.
