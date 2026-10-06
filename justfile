# Dinner Bell: every command lives here (CLAUDE.md "Commands"). `just` lists them.
set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := false

# OrbStack's docker CLI may not be on PATH in every shell.
export PATH := env_var("HOME") + "/.orbstack/bin:" + env_var("PATH")

# Repo scripts run on a modern Python via uv (the system python3 may be old).
py := "uv run --quiet --no-project --python 3.14"

default:
    @just --list --unsorted

# ---- setup and development ------------------------------------------------------------------

# Install tools and dependencies, git hooks, a local .env (fake Kroger) and the private-terms list
setup:
    #!/usr/bin/env bash
    set -euo pipefail
    for tool in uv pnpm gitleaks jq; do
      command -v "$tool" >/dev/null || { echo "Missing $tool: brew install $tool"; exit 1; }
    done
    (cd backend && uv sync --locked)
    (cd frontend && pnpm install --frozen-lockfile && pnpm exec playwright install chromium webkit)
    git config core.hooksPath .githooks
    if [ ! -f .env ]; then
      key="$(openssl rand -base64 48 | tr -d '\n/+=')"
      sed "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=$key|" .env.example > .env
      echo "Created .env (fake Kroger mode, development settings)."
    fi
    {{py}} scripts/private_scan.py setup

# Run the backend (auto-reload) and the Vite dev server together
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT
    (cd backend && uv run --env-file ../.env dinnerbell serve --reload --host 127.0.0.1) &
    (cd frontend && pnpm dev) &
    wait

# ---- checks (CI runs `just check`) -----------------------------------------------------------

# Format everything
fmt:
    cd backend && uv run ruff format . && uv run ruff check --fix .
    cd frontend && pnpm exec prettier --write .

# Lint and format checks, both halves
lint:
    cd backend && uv run ruff check . && uv run ruff format --check .
    cd frontend && pnpm exec eslint . && pnpm exec prettier --check .

# Type checks: pyright strict, tsc
typecheck:
    cd backend && uv run pyright
    cd frontend && pnpm exec tsc -b

# Unit and API tests (no network)
test:
    cd backend && uv run pytest -q -m "not kroger_live" --disable-socket --allow-unix-socket
    cd frontend && pnpm exec vitest run

# Regenerate the frontend's API types from the backend's OpenAPI schema
api-types:
    cd backend && uv run dinnerbell openapi --out ../frontend/src/api/openapi.json
    cd frontend && pnpm exec openapi-typescript src/api/openapi.json -o src/api/schema.d.ts

# Fail if the committed API types are stale
api-types-check:
    #!/usr/bin/env bash
    set -euo pipefail
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
    (cd backend && uv run dinnerbell openapi --out "$tmp/openapi.json")
    (cd frontend && pnpm exec openapi-typescript "$tmp/openapi.json" -o "$tmp/schema.d.ts" >/dev/null)
    diff -u frontend/src/api/openapi.json "$tmp/openapi.json"
    diff -u frontend/src/api/schema.d.ts "$tmp/schema.d.ts"
    echo "API types are up to date."

# Migrations: upgrade an empty database, compare with the models, run the migration tests
migrations-check:
    #!/usr/bin/env bash
    set -euo pipefail
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
    cd backend
    DATA_DIR="$tmp" uv run alembic upgrade head
    DATA_DIR="$tmp" uv run alembic check
    uv run pytest -q tests/test_migrations.py --disable-socket --allow-unix-socket

# VERSION is the only version; CHANGELOG has an Unreleased section
release-meta-check:
    {{py}} scripts/check_release_meta.py

# Everything a commit must pass
check: lint typecheck test api-types-check migrations-check release-meta-check

# ---- build, end-to-end, screenshots ------------------------------------------------------------

# Production frontend build
build:
    cd frontend && pnpm build

# End-to-end tests at phone (WebKit, Chromium) and desktop size
e2e: build
    cd frontend && pnpm exec playwright test

# Capture key screens (phone + desktop, light + dark) into .screenshots/ for review
screenshots: build
    cd frontend && SCREENSHOTS=1 pnpm exec playwright test screenshots --project=mobile-webkit --project=desktop-chromium
    @echo "Review every image in .screenshots/ before calling UI work done."

# ---- privacy -----------------------------------------------------------------------------------

# gitleaks (history + working tree) and the private-terms scan (tree + unpushed commits)
scan:
    gitleaks git --redact --no-banner .
    gitleaks dir --redact --no-banner .
    {{py}} scripts/private_scan.py tree
    {{py}} scripts/private_scan.py history

hook-pre-commit:
    gitleaks git --pre-commit --staged --redact --no-banner .
    {{py}} scripts/private_scan.py staged

hook-commit-msg FILE:
    {{py}} scripts/private_scan.py msg {{FILE}}

hook-pre-push RANGE:
    {{py}} scripts/private_scan.py range {{RANGE}}

# ---- release (run by the deploy skill; see .claude/skills/deploy) --------------------------------

# Build an amd64 image from git, run it and probe it
smoke-image REF="HEAD":
    scripts/smoke_image.sh {{REF}}

# The full release gate; stamps the tree it passed on
preflight:
    #!/usr/bin/env bash
    set -euo pipefail
    [ "$(git rev-parse --abbrev-ref HEAD)" = main ] || { echo "Release from main."; exit 1; }
    [ -z "$(git status --porcelain)" ] || { echo "Commit or discuss uncommitted changes first."; exit 1; }
    git fetch --quiet origin main
    [ "$(git rev-list --count HEAD..origin/main)" = 0 ] || { echo "main is behind origin/main."; exit 1; }
    just check
    just e2e
    just scan
    {{py}} scripts/private_scan.py context HEAD
    just smoke-image HEAD
    [ "$(docker context show)" = orbstack ] || { echo "Switch Docker to OrbStack: docker context use orbstack"; exit 1; }
    docker info --format '{{{{json .DriverStatus}}' | grep -q io.containerd.snapshotter.v1 \
      || { echo "Docker needs the containerd image store for multi-arch builds."; exit 1; }
    jq -e '.auths["https://index.docker.io/v1/"]' ~/.docker/config.json >/dev/null \
      || { echo "Log in to Docker Hub first: docker login -u scopexl"; exit 1; }
    git rev-parse 'HEAD^{tree}' > .git/dinnerbell-preflight
    echo "Preflight passed."

# Bump VERSION (patch|minor|major), roll the CHANGELOG, lock released migrations
bump LEVEL:
    {{py}} scripts/release.py bump {{LEVEL}}

# Commit the release files, tag vX.Y.Z and push branch + tag together
release-tag *ARGS:
    {{py}} scripts/release.py tag {{ARGS}}

# Build and push the multi-arch image for the current VERSION's tag
image:
    scripts/image_build.sh

# Verify the pushed image (both arches, tags agree, probes, private scan)
image-verify:
    scripts/image_verify.sh

# The whole release without Claude: preflight, bump, tag, smoke, push, verify
release LEVEL:
    just preflight
    just bump {{LEVEL}}
    just release-tag
    just smoke-image "v$(cat VERSION)"
    just image
    just image-verify

# ---- helpers ----------------------------------------------------------------------------------

# Show a backup's migration revision, app version and row counts
inspect-backup FILE:
    cd backend && uv run dinnerbell inspect-backup {{FILE}}

# Create a new migration (autogenerated against a temporary database at head)
db-revision MSG:
    #!/usr/bin/env bash
    set -euo pipefail
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
    cd backend
    DATA_DIR="$tmp" uv run alembic upgrade head
    DATA_DIR="$tmp" uv run alembic revision --autogenerate --rev-id "$(date -u +%Y%m%d%H%M)" -m "{{MSG}}"
