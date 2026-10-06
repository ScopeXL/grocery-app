# ADR 0019: Versioning with a VERSION file, SemVer, Keep a Changelog and annotated tags

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The reference apps hard-code "0.1.0" in four places and never bump it. Here, the owner needs to confirm that Portainer pulled the new image, and every release needs plain-English notes.

## Decision

- **One source of truth.** The root `VERSION` file holds `X.Y.Z`. `pyproject.toml` and `package.json` stay at `0.0.0`, and a check enforces that.
- **Where the version is read:**

  | Where | How |
  |---|---|
  | Backend | `/app/build-info.json`, written at image build: version, revision and created time |
  | Frontend | Vite injects `__APP_VERSION__` |
  | Docker | Build args: `VERSION`, `REVISION`, `CREATED`, `SOURCE_DATE_EPOCH` |

- **Where it's shown:**
  - `GET /api/version` returns `{version, revision, created}`.
  - Settings → About shows it.
  - The SPA shows "Update available" when its built version differs from the server's.
- **Bump level:**
  - Patch by default; minor for a new user-visible capability (each milestone is a minor release); major only when the owner asks.
  - 1.0.0 is the owner's call after M5.
- **CHANGELOG.md** follows Keep a Changelog 1.1, with sentences a household member can understand. Internal work collapses into one "Behind the scenes" line.
- **Tags.** Annotated `vX.Y.Z` git tags are never moved. Docker tags are `X.Y.Z`, `X.Y` and `latest`, and version tags are immutable on Docker Hub.

## Consequences

- The deploy skill (PLAN §11.10) owns all bumping and tagging.
- `release.py` also locks the released migrations (ADR 0021).
