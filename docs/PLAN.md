# Dinner Bell — plan

This is the current plan for Dinner Bell, a household meal-planning and grocery-list PWA. It is the single source for what we are building and how. Decisions and their reasoning live in [`adr/`](adr/README.md). Screens, flows and visual design live in [`UX.md`](UX.md). Working rules for AI sessions live in [`../CLAUDE.md`](../CLAUDE.md).

**Status:** M0 (foundation) shipped as 0.1.0, M1 (store, items and meals) as 0.2.0, M2 (plan and list) as 0.3.0 and M3 (shopping mode) as 0.4.0, all on 2026-10-06, and M4 (savings) as 0.5.0 on 2026-10-07. M5 (polish and online ordering) is next.

**Maintenance rule:** when a milestone ships, shrink its section to a one-line summary that points to the CHANGELOG. Keep this file about what is true now and what is left to do.

## Contents

1. [Purpose, priorities and success test](#1-purpose-priorities-and-success-test)
2. [Glossary](#2-glossary)
3. [Decisions index](#3-decisions-index)
4. [Architecture](#4-architecture)
5. [Data model](#5-data-model)
6. [API outline](#6-api-outline)
7. [Kroger integration](#7-kroger-integration)
8. [Quantity math, totals and recommendations](#8-quantity-math-totals-and-recommendations)
9. [Live updates and offline shopping](#9-live-updates-and-offline-shopping)
10. [Access, login and security](#10-access-login-and-security)
11. [Foundation and release](#11-foundation-and-release)
12. [Milestones](#12-milestones)
13. [Risks and unknowns](#13-risks-and-unknowns)
14. [Where this plan departs from the original brief](#14-where-this-plan-departs-from-the-original-brief)
15. [Ideas beyond v1](#15-ideas-beyond-v1)

---

## 1. Purpose, priorities and success test

Dinner Bell lets a household share one plan and one shopping list. Members plan meals, mostly dinners, and the app builds a merged shopping list with an estimated total from Kroger product data. They then shop it, in a Kroger store with an aisle-sorted, checkable list, or online by sending it to their Kroger cart.

The app is used mostly on phones, often one-handed in a store aisle with weak signal, by people who are not technical. Desktop is for bulk work.

**When trade-offs collide, use this priority order:**

1. Easy for a non-technical family member to use on a phone.
2. The shopping list and estimated total are correct.
3. Nothing private ever lands in the public repo or image.
4. Easy for a future AI session to understand and change safely.
5. Feature breadth.

**Success test:** a family member who has never seen the app plans a dinner, then checks off its items in the store, with no help or instructions.

## 2. Glossary

The app uses these words consistently in the UI, code and docs. Internal identifiers (UPC, SKU, productId, locationId) are never shown to users.

| User sees | Code name | Meaning |
|---|---|---|
| Item | `Item` (`items`) | Something the household buys, linked once to a Kroger product (photo, size, price, aisle) and reused by every dish that needs it |
| Main, Side | `Dish` (`dishes`, `role` = `main`/`side`) | A dish with item lines and amounts. The Meals tab lists both |
| Meal | `PlanMeal` (`plan_meals`) | One Main plus zero or more Sides, with an occasion, an optional day and a scale (×½, ×1, ×2) |
| Occasion | `Occasion` (tag) | Dinner (default), Breakfast, Lunch or Snack. A tag on dishes and planned meals |
| This week's plan | `Plan` (`plans`) | The meals currently planned. Only one plan is active |
| Shopping list | `ShoppingList` (computed, never stored) | Built from the plan: lines merged across meals and rounded up to whole packages, plus extras, with have-it lines shown but not counted |
| Extra | `PlanExtra` | Something added to the list that isn't tied to a meal (a Kroger item or plain text). Shows who added it |
| Usuals | derived from extras history | One-tap re-adds of frequent extras |
| Have it already | `have_it` override | The household already has it. Still listed, excluded from the total |
| Usual sides | `dish_pairings` | Sides learned per Main from what the household picks. Editable |
| Saved list | `Trip` (`trips`, `trip_items`) | A frozen snapshot of the list for one shopping trip. Checkable, and kept in history |
| Start shopping / shopping mode | an active `Trip` | The full-screen, aisle-ordered checklist |
| Couldn't find | trip item state `missed` | Moved to a group at the end of the list |
| Store section | `store_sections` | An aisle number or a department (Produce, Deli…) in the household's walking order |

## 3. Decisions index

The full reasoning for each decision is in the ADR it links to.

| ADR | Decision |
|---|---|
| [0001](adr/0001-stack-and-reference-apps.md) | FastAPI + async SQLAlchemy + SQLite + Alembic; React + TypeScript strict + Vite + TanStack. This mirrors the owner's reference apps, with listed fixes |
| [0002](adr/0002-one-container-one-worker.md) | One container, one uvicorn worker, serving the SPA and the API; SQLite in WAL mode on `/data` |
| [0003](adr/0003-access-through-reverse-proxy.md) | Phones reach the app over HTTPS through the owner's existing reverse proxy; the app enforces its own login |
| [0004](adr/0004-household-password-login.md) | One household password; per-device sessions; a "Who's using this?" picker; sign out other devices |
| [0005](adr/0005-local-multi-arch-images.md) | Images are built locally with buildx (OrbStack) from `git archive` of a tag, for amd64 + arm64, and pushed as `scopexl/dinner-bell` |
| [0006](adr/0006-plan-shape-sides-occasions.md) | The plan is a list with optional days; usual sides are learned; occasions are tags |
| [0007](adr/0007-amounts-and-quantity-math.md) | Amounts are package parts, counts, or weight/volume with exact units only; quantities are `Fraction`; money is integer cents |
| [0008](adr/0008-first-run-starts-empty.md) | The app starts empty, with a guided first dinner |
| [0009](adr/0009-kroger-cart-in-m5.md) | Send to Kroger cart is in v1 (M5), on the production API; add-only, with a double-add guard |
| [0010](adr/0010-one-store.md) | One store for now; store-scoped data allows more later |
| [0011](adr/0011-name-dinner-bell.md) | The app is named Dinner Bell |
| [0012](adr/0012-visual-direction-fridge-door.md) | The visual direction is "Fridge door" |
| [0013](adr/0013-license-mit.md) | MIT license |
| [0014](adr/0014-live-updates-sse.md) | Live updates use server-sent events; commands use REST |
| [0015](adr/0015-offline-shopping-sync.md) | Offline shopping: an IndexedDB snapshot, an idempotent op outbox, last-writer-wins |
| [0016](adr/0016-kroger-data-and-terms.md) | Kroger data is an expiring cache; only household data is durable |
| [0017](adr/0017-privacy-guardrails.md) | gitleaks plus a local private-terms scan, synthetic fixtures, screenshots never committed |
| [0018](adr/0018-generated-api-contract.md) | Frontend types are generated from OpenAPI, with a staleness check |
| [0019](adr/0019-versioning.md) | A `VERSION` file, SemVer, Keep a Changelog, annotated tags |
| [0020](adr/0020-photos-in-sqlite.md) | Meal photos are stored in SQLite as WebP |
| [0021](adr/0021-forward-only-migrations.md) | Migrations are forward-only and run at startup after a backup |
| [0022](adr/0022-git-identity-and-commits.md) | Commits use the noreply identity; commit when green; push only on deploy |
| [0023](adr/0023-ui-primitives-and-typescript-6.md) | UI primitives use platform features (no runtime style injection, so the strict CSP holds); TypeScript pinned to 6.0 |

---

## 4. Architecture

### 4.1 Runtime

One Docker image runs one process: `dinnerbell serve`. It starts uvicorn with **exactly one worker** (an invariant; see ADR 0002), which serves:

| Path | Response |
|---|---|
| `/api/*` | JSON, with `Cache-Control: no-store` |
| `/api/events` | Server-sent events (SSE) |
| `/assets/*` | Hashed build files with `max-age=31536000, immutable`; a missing asset returns 404, never `index.html` |
| Any other GET | `index.html` with `no-cache` (the SPA fallback) |

`/sw.js` and `/manifest.webmanifest` are also served with `no-cache`.

- SQLite lives at `/data/dinnerbell.db` in WAL mode. Backups go to `/data/backups/`.
- The app sits behind the owner's HTTPS reverse proxy. Forwarded headers are trusted only from `TRUSTED_PROXIES`.

### 4.2 Versions

These were checked on npm and PyPI on 2026-10-06 and get pinned in M0. Anything that doesn't work together falls back to the nearest compatible version, recorded in an ADR.

| Side | Versions |
|---|---|
| Python | 3.14; FastAPI 0.142; SQLAlchemy 2.1 (install `sqlalchemy[asyncio]`, since greenlet is no longer implicit); Alembic 1.20; pydantic 2.13; pydantic-settings 2.15; structlog 26; httpx 0.28; uvicorn 0.54; cryptography 50; Pillow 12; Hypothesis 6.168; pytest 9.1; ruff 0.16; pyright 1.1.414; tzdata |
| Frontend | Node 26 (`.node-version`); pnpm 12, pinned via `packageManager` (Node 25+ no longer bundles corepack); React 19.3; Vite 8; Tailwind 4.3; TanStack Router 1.170 and Query 5.104; vite-plugin-pwa 2.0; openapi-typescript 7.13 and openapi-fetch 0.17; Vitest 5; Playwright 1.63; ESLint 10 with typescript-eslint; Prettier; `@fontsource-variable/atkinson-hyperlegible-next` 5.3; lucide-react; workbox; idb and idb-keyval (M3). Nothing that injects styles at runtime ([ADR 0023](adr/0023-ui-primitives-and-typescript-6.md)) |
| TypeScript | 6.0, pinned: typescript-eslint doesn't support 7.x yet ([ADR 0023](adr/0023-ui-primitives-and-typescript-6.md)) |

### 4.3 Backend layout

The backend is organized by feature. Each feature package holds `models.py`, `schemas.py`, `service.py` and `router.py`, and its tests mirror it under `backend/tests/<feature>/`.

```
backend/
  pyproject.toml  uv.lock  .python-version  alembic.ini (CLI only)
  src/dinnerbell/
    __init__.py            empty, so the healthcheck import stays cheap
    __main__.py, cli.py    serve | check-config | migrate --dry-run | backup-now | inspect-backup | openapi | export
    boot.py                the startup sequence (§11.4)
    app.py                 create_app(lifespan=…): routers, middleware, SPA mount
    healthcheck.py         stdlib urllib probe used by the Docker HEALTHCHECK
    core/                  config (pydantic-settings), logging (structlog + redaction), crypto (HKDF, Fernet),
                           version, errors (one error envelope), clock (injectable), jobs (tiny scheduler)
    db/                    engine (pragmas, write lock), base (naming convention), types (FractionText, UUIDv7),
                           migrate, backup, export, instance_lock
    migrations/            env.py, script.py.mako, versions/, released.lock
    web/                   spa, headers (CSP etc.), csrf, errors
    events/                hub (SSE fan-out, ring buffer), router (/api/events)
    auth/                  password, sessions, ratelimit, devices
    household/             settings, members
    stores/                store search, active store, sections
    kroger/                api (Protocol), live, fake (+ fixtures/), http, tokens, oauth, cart, usage, cache
    catalog/               items and product links
    meals/                 dishes, dish items, pairings, photos
    planning/              plan, planned meals, extras, overrides, list building, recommendations
    shopping/              trips, trip ops, history, cart sends
    domain/                PURE: rational, units, sizes, money, models, amounts, listbuild, totals, recommend, snapshot
  tests/                   conftest.py, <feature>/…, domain/…, fixtures/db/<rev>.sql, smoke/test_kroger_live.py
```

**Rules**
- `domain/` imports only the standard library. A purity test checks its imports against an allowlist (§8.1).
- Services call `domain/`; routers call services.
- Attribution (who did what) always comes from the session's device, never from a request payload.

### 4.4 Frontend layout

```
frontend/
  package.json  pnpm-lock.yaml  vite.config.ts  tsconfig*.json  eslint.config.js  playwright.config.ts
  src/
    main.tsx  router.tsx  nav.ts  nav.check.ts   code-based TanStack Router; nav.check fails the build on dead links
    api/       openapi.json + schema.d.ts (generated, committed), client.ts (openapi-fetch wrapper), keys.ts (query keys)
    lib/       db.ts (idb), outbox.ts, events.ts (SSE), eventRouter.ts, connection.ts, clock.ts,
               wakeLock.ts, images.ts, persist.ts, format.ts
    ui/        Button, Sheet (native <dialog>), Toast with Undo, Checkbox, Stepper, ProductImage,
               EmptyState, TabBar, OfflinePill, MarkerStrike, AmountPicker (no runtime style injection)
    features/  onboarding, auth, plan, meals, list, shopping, history, settings
    styles/    tokens.css (Tailwind v4 @theme: design tokens defined once)
    sw.ts      service worker (vite-plugin-pwa injectManifest)
  e2e/         Playwright specs
```

**`client.ts`**
- Sends the `X-Dinner-Bell: 1` header on every mutating request (CSRF defence).
- Records clock samples from the `X-Server-Time-Ms` response header.
- Treats non-JSON responses, such as a proxy's 502 HTML page, as "server unreachable".

**TypeScript flags:** `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `isolatedModules`, `moduleResolution: bundler`.

---

## 5. Data model

**Conventions**
- Primary keys are UUIDv7 strings: time-ordered, and a client can generate them. Python 3.14 has `uuid.uuid7()`.
- Money is integer cents.
- Amounts, scales and sizes are exact fractions stored as TEXT, using `str(Fraction)` (`"3/8"`, `"169/10"`) through one `FractionText` TypeDecorator. Floats are never used for quantities or money.
- Timestamps are UTC; op timestamps are integer milliseconds. The `TZ` setting is used only for "Tonight", day boundaries and display.
- Enums are StrEnum values stored as VARCHAR.
- Undoable deletes are soft (`deleted_at` or `archived_at`) and restorable.
- Constraint names follow a MetaData naming convention, so Alembic batch mode can find them.

| Table | Columns (main ones) | Notes |
|---|---|---|
| `household` (1 row) | name, active_store_id, default_cart_modality (`PICKUP`/`DELIVERY`), price_max_age_minutes | A typed single row, not key-value |
| `app_meta` (1 row) | auth_epoch, password_fp, secret_key_check, last_boot_version | Changing the password, or a mismatched secret key, bumps `auth_epoch` and signs out every device |
| `members` | id, name, marker_color, sort, archived_at | Used for attribution only; not separate logins |
| `devices` | id, label, member_id, created_at, last_seen_at (written at most hourly), revoked_at | Backs "Sign out other devices" and the "Who's using this?" choice |
| `stores` | id, location_id (unique), chain, name, address fields, timezone, chain_domain, departments (JSON) | Filled from the Locations API |
| `store_sections` | id, store_id, key (`aisle:12`, `cat:produce`), label, sort_index, hidden | The walking order, editable per store |
| `kroger_product_cache` | (product_id, location_id) → payload (JSON), fetched_at, expires_at, cache_control_raw | Kroger data, kept only as a cache (§7.4). Parsed into typed objects in `kroger/`; expired rows are purged hourly |
| `items` | id, name, product_id?, upc?, size_text?, size_source (`parsed`/`household`), sold_by (`UNIT`/`WEIGHT`)?, each_weight_lb (FractionText)?, is_staple, section_override_key?, archived_at | The household's own data. `size_text` is the canonical `format_size` text, confirmed when linking or corrected ("Fix size"); `sold_by` is confirmed when linking (ADR 0016) |
| `dishes` | id, name, role (`main`/`side`), occasions (JSON list), servings?, photo_id?, notes?, recipe_url?, favorite, last_planned_at?, archived_at, created_at, updated_at | |
| `dish_items` | id, dish_id, item_id, amount_kind (`packages`/`measure`/`count`), amount (FractionText), unit?, position | |
| `dish_pairings` | main_id, side_id, times_chosen, last_chosen_at, pinned, hidden | Drives "usual sides" (M2). `pinned` and `hidden` record hand edits |
| `photos` | id, webp (BLOB, ≤1600 px), thumb (BLOB, ≤400 px), width, height, created_at | Re-encoded without metadata (no GPS). Included in backups and export (ADR 0020) |
| `plans` | id, status (`active`/`archived`), started_at, archived_at | Exactly one active plan |
| `plan_meals` | id, plan_id, main_id, day?, occasion, scale (FractionText: 1/2, 1, 2), position, added_by_member_id, created_at, deleted_at | |
| `plan_meal_sides` | plan_meal_id, side_id, position | Swapping a side changes one row |
| `plan_extras` | id, plan_id, item_id? or text?, quantity (FractionText, in the line's unit), note?, added_by_member_id, created_at, deleted_at | Covers the "Requests" idea: each extra shows who added it. Adding what's already an extra adds to it. Usuals come from this table's history: removed extras count, ones on the list now don't |
| `plan_item_overrides` | plan_id, item_id, have_it (true, false, or null for "not asked yet")?, qty_delta (FractionText)?, qty_delta_unit (`package`/`each`/`pound`)?, swap_product_id?, swap_upc?, swap_size_text?, swap_sold_by? | Overrides never edit a dish. Quantity overrides are stored as a delta (§8). A this-trip swap keeps the facts the household confirmed by choosing it, like an item's link (ADR 0016). Staples wait in the pantry check while have_it is null |
| `trips` | id, plan_id? (none for Shop this again), store_id, status + status_ts + status_by, created_by, created_at, estimate_cents, savings_cents, not_priced, prices_as_of, actual_total_cents?, finished_at?, version (gapless), fingerprint (the list it was saved from), product_cache_expires_at | Status is last-writer-wins (§9). One active saved list per plan: saving again updates it |
| `trip_items` | id, trip_id, line_key (item id or `extra:<id>`), item_id?, name, product_id?, upc?, image_url?, product_url?, size_text?, qty_text, quantity, unit, unit_cents?, line_cents?, regular_cents?, on_sale, sale_ends?, section_key?, section_label?, section_order, aisle_side?, bay, used_by (JSON), warnings (JSON), position; state + state_ts + state_by; note + note_ts + note_by; version; removed_at? | Frozen snapshot apart from state and note, which are separate last-writer-wins fields. Updating the saved list refreshes the snapshot, keeps states and notes, and marks to-do lines no longer needed as removed (with a new version, so phones hear it) |
| `applied_ops` | op_id (PK), trip_id, kind, client_id, member_id, client_ts, effective_ts, received_at, result, reason | Makes ops idempotent; pruned after 60 days |
| `kroger_tokens` (1 row) | access_enc, access_expires_at, refresh_enc, refresh_obtained_at, scope, connected_by, status (`connected`/`needs_reconnect`), version | Fernet-encrypted (§10). Always present; empty until connected |
| `kroger_oauth_states` | state, code_verifier, device_id, expires_at, used_at | M5 |
| `cart_sends` | id, trip_id, trip_item_id, upc, quantity, modality, sent_at, outcome (`added`/`failed`/`unknown`) | Guards against double-adds |
| `kroger_api_usage` | api, window_started_at, calls, blocked_until?, last_429_at?, probe_backoff_s? | Tracks the daily limits; `probe_backoff_s` is the current wait while probing an unknown window |

A trip is a snapshot on purpose: later edits to meals or prices must not change a list someone is shopping from.

---

## 6. API outline

**Conventions**
- Everything is under `/api`.
- Errors use one envelope: `{"error": {"code": "...", "message": "plain-English text"}}`.
- Mutating requests must carry `X-Dinner-Bell: 1`. If `Origin` is present it must equal `APP_BASE_URL`.
- Every response carries `X-Server-Time-Ms`.
- Amounts travel as strings (`"3/8"` or `"0.375"`). JSON floats are rejected for amounts.

| Area | Endpoints |
|---|---|
| Meta | `GET health` (public; 200 only after startup completes and `SELECT 1` succeeds), `GET version` (public: version, revision, created), `GET admin/diagnostics` (signed in: schema revision, Kroger mode, backup state, resolved client IP and forwarded headers) |
| Auth | `POST auth/login`, `POST auth/logout`, `GET auth/session`, `PUT auth/member` (stores the member on the device), `GET auth/devices`, `DELETE auth/devices/{id}`, `POST auth/devices/sign-out-others` |
| Household | `GET` / `PATCH settings`; members `GET`, `POST`, `PATCH`, archive; `GET export` |
| Backups | `GET admin/backups`, `POST admin/backups/run`, `GET admin/backups/{name}` (download) |
| Stores | `GET stores/search?zip=`, `PUT stores/active`, `GET` / `PUT stores/{id}/sections` |
| Kroger | `GET kroger/products?q=` (3+ characters; short server-side cache), `POST kroger/connect` (M5; returns the authorize URL), `GET kroger/callback` (M5), `DELETE kroger/connection` |
| Items | `GET items?q=` (household items first), `POST items`, `PATCH items/{id}` (link product, correct size, each-weight, staple flag), archive and restore |
| Dishes | `GET dishes?role=&occasion=&q=&favorite=`, `POST dishes`, `GET` / `PATCH dishes/{id}`, `PUT dishes/{id}/items`, `POST dishes/{id}/duplicate`, archive and restore, `PUT dishes/{id}/photo`, `GET` / `PUT dishes/{id}/usual-sides` |
| Plan | `GET plan` (meals, the computed list, extras, usuals and totals, priced live), `POST plan/meals`, `PATCH plan/meals/{id}` (swap main, day, occasion, scale), `PUT plan/meals/{id}/sides`, `DELETE plan/meals/{id}` and `POST …/restore`, extras (`POST`, `PATCH`, `DELETE` and restore), `PUT plan/items/{itemId}` (have-it, quantity, product swap for this trip or always), `GET plan/items/{itemId}/alternatives` (with unit prices), `POST plan/new-week` and `POST plan/new-week/undo`, `GET plan/recommendations` (M4), `POST plan/repeat?from={planId or tripId}` (M3). Every change answers with the whole plan, so screens update from the response. Prices are fetched live on every read, so there is no refresh endpoint |
| Trips | `POST trips` (save the plan's list, or update its saved list: 201 or 200), `GET trips[?before=]` (active, then finished a page at a time), `GET trips/{id}[?since_version=N]`, `POST trips/{id}/ops` (batched, idempotent; §9.2), `POST trips/{id}/shop-again`, `POST trips/{id}/send-to-cart` (M5). Walking order: `GET` / `PUT stores/active/sections`. `POST plan/repeat {trip_id}` plans a trip's meals again |
| Events | `GET events?since=epoch:seq` (SSE; §9.3) |
| Test only | `/_test/{reset,seed,drop-streams,revoke-sessions}`, available only when `DINNERBELL_TEST_MODE=1`. Startup refuses that flag unless `APP_BASE_URL` is localhost |

Finishing and reopening a trip are ops (`trip.finish` and `trip.reopen`), so they work offline.

---

## 7. Kroger integration

### 7.1 Verified facts

These were verified on 2026-10-06 against Kroger's developer docs, FAQ, Terms and the official OpenAPI specs: Products v1.3.0, Locations v1.2.3, Cart v1.2.3, Identity v1.2.3 and Authorization v1.0.17. The developer site renders its pages in the browser, so the text came from its content and spec endpoints. Anything still unconfirmed is listed in §13.

**Hosts and environments**
- Production is `https://api.kroger.com/v1/`; certification is `https://api-ce.kroger.com/v1/`. Each environment needs its own app registration.
- Certification can't test the cart or customer sign-in, because its login site is internal to Kroger.
- **We use production only.**

**Auth**
- `POST /v1/connect/oauth2/token`, form-encoded, with `Authorization: Basic base64(client_id:client_secret)`. Access tokens last 1800 s.
- The client-credentials grant works for Products (scope `product.compact`) and Locations (no scope).
- Cart needs the authorization-code grant with scope `cart.basic:write`. The FAQ shows that client credentials are refused for it.
- Authorize endpoint: `GET /v1/connect/oauth2/authorize` with `scope`, `client_id`, `redirect_uri`, `response_type=code`, and optionally `state`, `code_challenge` and `code_challenge_method=S256` (PKCE, supported since May 2026).
  - An optional `banner` brands the consent page (e.g. `kroger`, `ralphs`).
  - `redirect_uri` must match a registered URI exactly.
  - A refused consent returns `error=access_denied`.
- **Refresh tokens rotate:** each use returns a new one, and reusing an old one returns 400. Their lifetime is documented inconsistently ("6 months" in the FAQ, "typically 24 hours" in the spec), and one client reports occasional missing rotations. Send Basic auth on refresh.
- Identity (`/v1/identity/profile`) returns only a profile ID, and the Acceptable Use Policy forbids mapping data to it. **We don't use Identity.**

**Locations**
- `GET /v1/locations` takes:
  - `filter.zipCode.near` (or lat/long);
  - `filter.radiusInMiles` (1–100, default 10);
  - `filter.limit` (1–200);
  - `filter.chain`, `filter.department`, `filter.locationId` (comma-separated).
- There is no pagination and no city/state search.
- `locationId` is 8 characters: a 3-digit division followed by a 5-digit store number.
- Responses include:
  - `locationId`, `storeNumber`, `divisionNumber`, `chain`, `name`, `phone`;
  - `address{addressLine1, addressLine2, city, county, state, zipCode}`;
  - `geolocation`;
  - `hours{timezone, gmtOffset, open24, monday…sunday}` (the spec spells it `Open24`, so parse case-insensitively);
  - `departments[]{departmentId, name, phone?, hours?}`.
- Fuel centers appear with chain `SHELL COMPANY`. **Filter them out.**
- `GET /v1/chains` returns `name`, `divisionNumbers` and `domain`, e.g. `kroger.com` (added in v1.2.3).
  - Product link: `https://www.{domain}{productPageURI}`.
  - Fall back to `kroger.com` when the chain or domain is missing.

**Products**
- `GET /v1/products` needs one of `filter.term`, `filter.brand` or `filter.productId`.
- `filter.term`: at least 3 characters and at most 8 words. Search is fuzzy and popularity-ranked, so results vary from call to call.
- `filter.locationId` is required to get price, aisle, inventory and fulfillment.
- `filter.limit`: 1–50. `filter.start`: 1–250.
- `filter.productId` takes up to 50 comma-separated 13-digit IDs, but the spec says "all other query parameters are ignored". **Whether `locationId` still applies is unverified** (§13).
- `GET /v1/products/{id}?filter.locationId=` accepts a productId or UPC.
- Product fields:
  - `productId`, `upc`, `productPageURI`, `brand`, `categories[]`, `description`, `countryOrigin`, `temperature`, `itemInformation`;
  - `aisleLocations[]{number, side, description, bayNumber, shelfNumber, sequenceNumber, numberOfFacings, shelfPositionInBay}`;
  - `images[]{perspective, featured, sizes[]{size: thumbnail|small|medium|large|xlarge, url}}`.
- Item fields (`items[]`):
  - `itemId`, `size` (string), `soldBy` (`UNIT`/`WEIGHT`; case varies);
  - `inventory.stockLevel` (`HIGH`/`LOW`/`TEMPORARILY_OUT_OF_STOCK`, or absent);
  - `fulfillment{curbside, delivery, inStore|instore, shipToHome|shiptohome}` (key casing varies);
  - `price{regular, promo, regularPerUnitEstimate, promoPerUnitEstimate, effectiveDate?, expirationDate?}`, `nationalPrice`.
- **Price quirks:**
  - `promo` is a sale price, not a discount amount. Missing or `0` means no promo.
  - `regularPerUnitEstimate` is unreliable (one capture shows 0.0995 against a 2.19 regular).
- **Fresh departments** often have an empty aisle list, or a placeholder (`PRODUCE`, number `0`). An aisle location means the store has a dedicated spot for the item, not that it's in stock.
- Loose produce uses PLU-based IDs (e.g. `0000000004011`).
- Image URLs follow `https://www.kroger.com/product/images/{size}/{perspective}/{productId}`.

**Cart**
- `PUT /v1/cart/add` with `{"items":[{"upc":"<13>","quantity":<int>,"modality":"PICKUP"|"DELIVERY"}]}` returns **204**.
- **Add-only.** We can't read, verify or clear the cart.
- It takes no location parameter: items go to the store selected in the shopper's Kroger account.
- **Never retry it blindly; a retry can add items twice.**

**Rate limits**
- Limits are per client ID, over a rolling 24 h from the first call to an endpoint:

  | API | Calls per day |
  |---|---|
  | Products (search and by-ID share one bucket) | 10,000 |
  | Cart | 5,000 |
  | Identity | 5,000 |
  | Locations (each of locations, chains, departments) | 1,600 |

- A 429 means the day's limit is used up.
- **Use a Kroger app registered only for Dinner Bell**, so other tools don't use up its limits.

**Terms, Acceptable Use and branding** (the constraints on this design)

| Term | What it means here |
|---|---|
| Don't keep cached copies longer than the cache header permits, and don't build databases from the data | §7.4 and ADR 0016 |
| Display product data exactly as returned | Show Kroger's own descriptions and size strings, never rewritten |
| Display images in their original form: no cropping, filters or overlays | `ProductImage` is the only way product photos are drawn |
| Don't track, share or store data derived from customer searches | Search results stay in memory for ≤60 s; search terms are never persisted or logged |
| Don't compare products or prices with other retailers | We don't |
| Provide a privacy policy | `PRIVACY.md`, plus About in the app |
| No "Kroger" in the app name and nothing that sounds like it; no implied endorsement; a logo that doesn't resemble Kroger's (avoid Kroger blue and the oval) | ADR 0011 and ADR 0012; the not-affiliated note in README and About |
| Developer credentials may not be embedded in open-source projects | Credentials live in env vars only |
| Make it clear which cart items go to | The Send sheet says so |
| Don't add items without the customer's knowledge | Cart adds happen only on an explicit tap |
| Customer cart data should be deleted when shopping is finished | `cart_sends` keeps only what's needed to prevent double-adds, and is pruned with old trips |

### 7.2 Client

- **One interface:** a `KrogerApi` Protocol (`search`, `get_product`, `get_products`, `locations`, `chains`, `add_to_cart`, `authorize_url`, `exchange_code`, `refresh`) with two implementations, chosen by `KROGER_MODE`:
  - **`live`:** the real client.
  - **`fake`:** synthetic fixtures and a simulated OAuth flow (`/api/kroger/fake-authorize`). The UI shows a small demo banner.

  Tests, e2e runs and screenshots always use `fake`. pytest disables sockets, and the live client refuses to construct under pytest unless the test is marked `kroger_live`.
- **HTTP:** one `httpx.AsyncClient`.
  - Connect timeout 5 s, read 10 s, no redirects, `User-Agent: DinnerBell/<version>`.
  - JSON is parsed with `parse_float=Decimal` and becomes integer cents at the boundary.
- **Retries:**
  - GETs and the app-token POST: retry on connect errors, read timeouts and 500/502/503/504. 3 attempts, full-jitter backoff (0.5 s base, 4 s cap), honoring `Retry-After`.
  - Code exchange and refresh: retry only on errors that prove the request never left (connect error or connect timeout).
  - **Cart add: never retried.** A timeout marks the item "unknown — check your Kroger cart".
- **App token:**
  - Kept in memory; refreshed when less than 60 s remain.
  - A single-flight `asyncio.Lock` with a re-check inside the lock.
  - On a 401: one forced refresh, then one retry.
- **Usage counter** (`kroger_api_usage`):
  - Counts per API bucket.
  - A 429 sets `blocked_until` to the window start + 24 h. If the window start is unknown, use now + 1 h, then single probes doubling up to 6 h.
  - While blocked, no calls go out and the API returns `{"error":{"code":"kroger_daily_limit","retry_at":…}}`.
  - The UI shows one quiet line: "Store search is paused until about 3:40 PM — your list still works."

### 7.3 Stores and sections

**Choosing a store**
1. Settings (or first run) searches by ZIP (`limit=20`, fuel centers removed). Each result shows name, address and distance.
2. Choosing one stores the row in `stores` and fetches `/chains` once for the domain.
3. Sections are seeded from the store's departments plus a default perimeter order: Produce first, then Bakery and Deli, then the aisles in ascending order, then Meat & Seafood, Dairy and Frozen last.

**Assigning an item to a section** (first rule that applies):
1. The household's `section_override_key` on the item.
2. Aisle `number` > 0 → `aisle:<n>`, labelled "Aisle 12, left side" from `side`.
3. Else the first matching Kroger category → `cat:<slug>`.
4. Else `cat:other`.

**Sorting**
- Within an aisle, sort by `bayNumber`, then by name.
- The household reorders sections with up/down buttons (plus a drag handle as a shortcut) in Settings → Store walking order.

### 7.4 Products, search, caching and terms (ADR 0016)

- **Search:**
  - The SPA debounces for 300 ms and needs at least 3 characters (8 words maximum).
  - The server caches results in memory, keyed by (normalized term, store, page), for min(60 s, what the headers permit), and coalesces identical in-flight requests.
  - Results show the uncropped photo, description, size and price.
- **Product cache** (`kroger_product_cache`):
  - `expires_at` comes from `max-age` minus `Age`, or from `Expires`.
  - With `no-store`, `no-cache` or no header, **nothing is persisted.** That holds until the M1 smoke test records what Kroger actually sends, in the "verified" table in `docs/KROGER.md` (written in M0).
  - Expired rows are purged hourly.
- **Durable data is only the household's own:**
  - item names;
  - the product link (productId/UPC);
  - the household-confirmed package size and whether it's sold by unit or by weight, and the each-weight;
  - dish amounts, plans and trips.
- **Only linked products are cached.** Search results stay in memory; products enter `kroger_product_cache` only when an item links to them.
- **Refreshing prices:**
  - Opening the plan or list refreshes the prices used there if they're older than `price_max_age_minutes` (default 120) or past `expires_at`.
  - Refresh uses `filter.productId` batches of 50: M1's smoke test confirmed batches return store prices and aisles. (`BATCH_INCLUDES_PRICES = False` falls back to `GET /products/{id}?filter.locationId=` at concurrency 4.)
  - Kroger sends no freshness headers on product data, so nothing is stored: every screen that shows prices fetches them live, in batches (docs/KROGER.md).
  - The total shows "prices as of" (§8).
- **Trip snapshots:**
  - An active trip holds everything shopping mode needs, including product names, image references and aisles. That's temporary storage for the trip.
  - When a trip finishes, `product_cache_expires_at` is recorded. After it passes, a job clears the Kroger descriptive fields (description, image reference, aisle).
  - The household's record stays: item names, quantities, estimates and totals. Viewing old history re-fetches product details when online.
- **Images:**
  - Hot-linked from Kroger's image host (CSP `img-src https://www.kroger.com/product/images/`) and never stored server-side.
  - For offline trips, the service worker keeps a bounded, expiring copy on the phone (§9.6).

### 7.5 Cart and account linking (M5)

**Connect Kroger** (Settings)
1. `POST /api/kroger/connect` creates a `kroger_oauth_states` row: a 32-byte `state`, a 64-byte PKCE verifier, the device, and a 10-minute expiry. It returns the authorize URL (`scope=cart.basic:write`, S256 challenge, `state`, `banner` from the store's chain).
2. The SPA navigates there. Kroger redirects to `KROGER_REDIRECT_URI`, which must equal `APP_BASE_URL + "/api/kroger/callback"` and be registered on the Kroger app.
3. `GET /api/kroger/callback` checks the `state` row exists and is unexpired, and marks it used before anything else.
   - If a session cookie is present, it must belong to the device that started the flow.
   - A missing session is tolerated: iOS can finish the flow in a different cookie jar, and the single-use, 256-bit state is the capability.
   - It then exchanges the code (Basic auth + `code_verifier`) and redirects with 303 to `/settings?kroger=connected` (or `=failed`).

**Tokens**
- Access and refresh tokens are stored Fernet-encrypted in `kroger_tokens`.
- **Refresh is single-flight.** It re-reads the row inside the lock, then:
  - On 200: stores the new access token and the new refresh token in one `BEGIN IMMEDIATE` update, guarded by `version`. If no new refresh token comes back, it keeps the old one and logs `refresh_not_rotated`.
  - On `invalid_grant`: sets `needs_reconnect`, wipes the tokens, publishes `settings.changed`, and Settings shows a "Reconnect Kroger" banner.
  - On an ambiguous failure: keeps the token and backs off.
- Every refresh logs the token's age, to settle the real lifetime.
- **Disconnect** deletes the tokens and any OAuth states.

**Send to cart** (a saved list)
1. A sheet asks "Pickup or delivery?" (defaulting to the household setting). It says: "Items go to the store chosen in your Kroger account. Review and check out in the Kroger app."
2. It lists the lines that have a UPC; unlinked lines are listed as "not sent".
3. Sending writes `cart_sends` rows with `outcome=unknown`, then calls `PUT /cart/add` in chunks.
   - A 204 marks the chunk `added`.
   - A 4xx marks it `failed`, with the reason.
   - A timeout leaves it `unknown`.
4. The result reads "Added 27 items to your Kroger cart." It lists failed or unknown items with a **Send these again** button covering only those.
5. Items already marked `added` are never re-sent automatically. A deliberate "Send again anyway" exists, behind a second confirmation sheet; it is the one place where confirming beats undo, because cart adds can't be undone.

### 7.6 Smoke test and fixtures

- **`just smoke-kroger`:** runs about 4 real calls (token, locations by the ZIP in the local `.env`, product search, product by ID).
  - It needs `KROGER_LIVE=1` and credentials in the local `.env`; otherwise it skips.
  - It prints only status codes, cache and rate headers, image URL prefixes and field shapes. Never payloads.
  - It answers the open questions in §13: batch pricing, cache headers, 429 shape, image hosts.
- **Fixtures** (`kroger/fixtures/*.json`) are synthetic:
  - product names like "Sample Whole Milk"; UPCs `00000000000NN`; location `99999001`; chain "SAMPLE MARKET";
  - SVG placeholder images served locally;
  - the real response *shapes*, including casing quirks, missing promos and placeholder aisles.
  - sale dates written for 2026-10-06 that move with the clock, so the fake store's sales are always current (tests on a fixed clock see them as written; e2e runs on the real clock see the same sales).

---

## 8. Quantity math, totals and recommendations

The hardest correctness problem in the app: turning "how much a meal needs" into "how many packages to buy". Everything here lives in `backend/src/dinnerbell/domain/`, is pure, and is the most heavily tested code in the repo (ADR 0007).

### 8.1 Representation rules

1. **Quantities are always `fractions.Fraction`.** Every constructor goes through `q()`, which raises `TypeError` on a float or bool.
   - Storage: canonical `str(Fraction)` text.
   - API input: strings such as `"3/8"` or `"0.375"`; JSON floats are rejected.
   - Decimal text can't hold ⅓ cup or 1/6 fl oz, and floats can't hold anything exactly.
2. **Money is integer cents.**
   - Kroger JSON is parsed with `parse_float=Decimal`.
   - Rounding happens in exactly two places, both half-up:
     - each weight-priced line (pounds × ¢/lb);
     - the displayed "about $N".
   - Unit-priced lines are integer × integer and never round.
   - Never use Python's `round()`, which rounds half to even.
3. **Merge, then round once.** Sum the exact shares per item across all meals, dishes and lines, then round up a single time.
4. **Loose produce and meat sold by the pound are never rounded to whole packages.** Counts round up to whole pieces, weights round up to the next ¼ lb, and the two are added.
5. **Unknowns stay visible.** An amount that can't be converted makes the line "at least N".
   - The lower bound counts toward the total, and the line counts in the "not priced" tally.
   - Every function is monotone: adding a meal never lowers any line or the total.
6. **Pure means pure:**
   - `now` is passed in and must be timezone-aware.
   - `test_purity.py` walks the syntax tree and allows imports only from `fractions`, `decimal`, `dataclasses`, `enum`, `typing`, `collections.abc`, `datetime`, `math`, `re`, `unicodedata`, `itertools` and `functools`.
   - It bans `now()`, `today()`, `time()` and `random`.

**Exact unit constants** (within a dimension only; weight ↔ volume is never converted):

| Dimension | Unit | Value |
|---|---|---|
| Mass | oz | 28.349523125 g (exact) |
| Mass | lb | 16 oz |
| Mass | kg | 1000 g |
| Volume | fl oz | 29.5735295625 ml (exact) |
| Volume | tsp | fl oz / 6 |
| Volume | tbsp | fl oz / 2 |
| Volume | cup | 8 fl oz |
| Volume | pint, quart, gallon | 16, 32 and 128 fl oz |
| Volume | l | 1000 ml |

### 8.2 Modules

```python
# rational.py   exact; no float accepted anywhere
def q(x: int | str | Decimal | Fraction) -> Fraction          # TypeError on float/bool
def ceil_to(x: Fraction, step: Fraction) -> Fraction           # ceil(x/step)*step
def round_half_up(x: Fraction) -> int                          # floor(x + 1/2), x >= 0
def to_text(x: Fraction) -> str; def from_text(s: str) -> Fraction
def to_mixed(x: Fraction) -> str                               # how people write it: "1 1/2"

# units.py      exact and invertible within a Dimension; never across
class Dimension(StrEnum): MASS; VOLUME; COUNT
class Unit(StrEnum): G; KG; OZ; LB; ML; L; FL_OZ; TSP; TBSP; CUP; PT; QT; GAL; EACH
@dataclass(frozen=True, slots=True) class Quantity: value: Fraction; unit: Unit
def convert(x: Quantity, to: Unit) -> Quantity                 # raises DimensionMismatch
def ratio(a: Quantity, b: Quantity) -> Fraction

# sizes.py      parse_size is total (never raises); values > 0; parse(format(s)) == s
@dataclass(frozen=True) class PackageSize:
    count: Fraction | None        # pieces per package: "6 ct"->6, "12 x 12 fl oz"->12, "each"->1
    measure: Quantity | None      # total content: "12 x 12 fl oz"->144 FL_OZ
    approximate: bool = False     # "about 1.25 lb"
    container: Container | None = None   # "3 lb bag" -> BAG, so the preview can say "the 3 lb bag"
@dataclass(frozen=True) class Unparseable: text: str; reason: ParseFail   # EMPTY|RANGE|UNKNOWN_UNIT|NON_POSITIVE|MULTIPLE|TRAILING|TOO_LARGE
def parse_size(text: str | None) -> PackageSize | Unparseable  # each part <= 10^9, so formats stay short
def format_size(s: PackageSize) -> str
def size_label(s: PackageSize) -> str                          # "12 x 12 fl oz": no "about", no container

# money.py      cents are ints >= 0; effective <= regular
@dataclass(frozen=True) class PriceInfo:
    regular: int | None; promo: int | None
    promo_from: datetime | None; promo_until: datetime | None   # aware, half-open [from, until)
    each_estimate: Fraction | None                              # regularPerUnitEstimate, in cents
    fetched_at: datetime
def dollars_to_cents(d: Decimal | str | None) -> int | None    # None or <= 0 -> None
def promo_valid(p: PriceInfo, now: datetime) -> bool
def effective_cents(p: PriceInfo, now: datetime) -> int
def about_dollars(cents: int) -> int
def headline_parts(t: Totals, as_of_local: str) -> Headline     # total, savings, prices_as_of, before_tax, not_priced
def headline(t: Totals, as_of_local: str) -> str             # the same, one per line; savings under $10 keep their cents

# models.py     SoldBy, Product(product_id, size_text, sold_by, price), Item(id, name, size_override,
#               each_weight), AmountKind {PACKAGES, MEASURE, COUNT}, Amount(kind, value, unit) with
#               .scaled(k), effective_size(item, product), InvalidAmount (with a plain .message),
#               Flag {NO_PRODUCT; NO_PRICE; SIZE_UNKNOWN; NEEDS_EACH_WEIGHT; NOT_CONVERTIBLE;
#               EST_EACH_WEIGHT; SWAPPED; APPROX_SWAP; OVERRIDDEN; OVERRIDE_STALE; SHORT; HAVE_IT; ON_SALE}
#               (built in M1, so amounts and the M2 list builder share them)
#   M2 adds:    DishLine(item_id, amount), Dish(id, name, lines), Meal(id, main, sides, scale) (day and
#               occasion stay in the API), PurchaseUnit {PACKAGE, EACH, POUND}, QuantityOverride(delta, unit),
#               Extra(id, item_id | text, quantity), PlanInput(meals, items, products, have_it, overrides,
#               swaps, extras): immutable, validated, with .with_meal(m)

# amounts.py    the picker only offers kinds that convert; validate rejects the rest
def amount_options(item: Item, product: Product | None) -> AmountOptions
def validate_amount(a: Amount, item: Item, product: Product | None) -> None   # raises InvalidAmount
def share_text(a, item, product) -> str | None                 # "About 3/8 of the 16 oz package"
def share_cost(a, item, product, now) -> int | None            # the amount's share, not the rounded buy
def resolve_each_weight(item, product) -> tuple[Fraction | None, bool]   # (lb, came_from_kroger_estimate)
def contribution(a, item, product, original, swapped) -> Contribution    # packages, lb, each, unconverted, flags

# listbuild.py  one line per item; qty >= need unless SHORT; overshoot < 1 package / 1 piece / 1/4 lb
def build_list(plan: PlanInput, now: datetime) -> ShoppingList     # lines sorted by (label.casefold(), key)
# Line: key, item_id, label, unit, need, computed (before the override), quantity, extra, at_least,
#       leftover (+ leftover_count, leftover_measure), each_weight (+ _estimated), product_id, size (of the
#       product used), unit/regular_unit/cost/regular/savings cents, price_fetched_at, unconverted,
#       used_by (MealUse(meal_id, dish_names), in the order meals were added), flags
# An "at least" line buys at least one step (a package, a piece, or 1/4 lb or one piece's weight).
def quantity_text(line, size) -> str; def quantity_words(unit, quantity, size) -> str   # "2 boxes", "1 3/4 lb"
def unit_price(product, now) -> UnitPrice | None                   # per oz, fl oz, piece or lb: "$0.25 per oz"

# totals.py     total + savings == regular_total; all >= 0
@dataclass(frozen=True) class Totals: total: int; savings: int; regular_total: int
    not_priced: int; needs_check: int; have_it: int; prices_as_of: datetime | None   # OLDEST fetched_at among priced lines
def summarize(lines) -> Totals

# recommend.py  deterministic; marginal cost >= 0; at most `limit` results
def marginal_cost(plan, dish, now) -> tuple[int, int]          # (added cents, count of new unpriced items)
def recommend(plan, candidates, now, *, limit=3, min_value_cents=100, name_min_cents=25) -> tuple[Recommendation, ...]

# (no snapshot.py: a saved list's snapshot is its trip_items rows, made from the List's own lines in
#  shopping/service.py; L17 lives in tests/test_shopping.py)
# listbuild.price_quantity(unit, quantity, product, each_lb, now) re-prices a saved amount (Shop this again)
```

### 8.3 Size parser

**Normalize first:**
- NFKC.
- Turn vulgar fractions into text (`½` → `1/2`, so `1½` → `1 1/2`). Map `⁄` → `/` and `×` → `x`.
- Lowercase.
- Delete `( … )` groups, so the rounded metric text in "16 fl oz (473 mL)" is ignored.
- `fl. oz.` → `fl oz`. Drop periods except decimal points. Collapse whitespace.
- A leading `about | approx(imately) | avg | average | ~` sets `approximate`.

```
NUM       := \d+(\.\d+)? | \.\d+ | \d+/\d+ | \d+ \d+/\d+
MASS      := oz|ounces?|lbs?|pounds?|g|grams?|kg|kilograms?          ("oz" is ALWAYS weight)
VOL       := fl ?oz|fluid ounces?|ml|millilit(er|re)s?|l|lit(er|re)s?|gal|gallons?|qt|quarts?|pt|pints?|cups?|tbsp|tsp
COUNT     := ct|count|each|ea|pk|packs?|pieces?|pcs?|dozen|dz|rolls?|cans?|bottles?|bags?|bunch(es)?|heads?|ears?|loaf|loaves|sticks?
CONTAINER := bag|box|pkg|package|can|jar|bottle|carton|tub|tray|container|pouch|clamshell
size      := multipack | compound | simple | "each" | "ea" | "per lb"
multipack := NUM (x | (ct|pk|pack|count) /) NUM (MASS|VOL|COUNT) [CONTAINER]
compound  := NUM (lb|lbs|pounds?) NUM (oz|ounces?)            -> total in oz
simple    := NUM (MASS|VOL) [CONTAINER] | NUM COUNT            (dozen/dz x 12)
```

Anything else is `Unparseable`: ranges (`3-4 lb`), two sizes, unknown units (`cu ft`), values ≤ 0, trailing text, "Varies".

| Input | Parsed |
|---|---|
| `16 oz` · `2 lb` · `0.75 lb` | 16 oz · 2 lb · 3/4 lb |
| `6 ct` · `each` · `1 each` · `1 ea` · `1 dozen` | count 6 · 1 · 1 · 1 · 12 |
| `1 gal` · `1/2 gal` · `½ gal` | 1 gal · 1/2 gal · 1/2 gal |
| `64 fl oz` · `16.9 FL. OZ.` | 64 fl oz · 169/10 fl oz |
| `12 x 12 fl oz` | count 12 + 144 fl oz |
| `6 ct / 16.9 fl oz` | count 6 + 507/5 fl oz |
| `8 x 1.5 oz` · `2 x 6 ct` | count 8 + 12 oz · count 12 |
| `3 lb bag` · `16 fl oz (473 mL)` · `1 lb 8 oz` | 3 lb · 16 fl oz · 24 oz |
| `about 1.25 lb` | 5/4 lb, approximate |
| `64 oz` (juice) | 64 oz as a **weight**; the household corrects it to fl oz |
| `Varies` · `""` · `None` · `3-4 lb` · `2 cu ft` · `0 oz` · `12 oz, 2 ct` | Unparseable |

### 8.4 Algorithms

**Amount → share** (`contribution`). `p` is the product used for this trip; `orig` is the item's own product.

```
direct(a, item, p):
  if p is None:  PACKAGES -> packages = a.value;  COUNT -> each = a.value;  else None
  if p.sold_by is WEIGHT:
     MEASURE(MASS) -> lb = convert(a, LB)
     COUNT         -> each = a.value
     PACKAGES      -> lb = a.value * (size_lb(p) or 1)          # Kroger prices weight items per 1 lb
     else None                                                  # never volume<->weight
  s = p.size                                                    # sold by UNIT
  PACKAGES -> packages = a.value                                # works even when s is None
  MEASURE  -> same dimension as s.measure: ratio(a, s.measure)
              elif s.count and item.each_weight and a is MASS: lb(a) / each_lb / s.count
  COUNT    -> s.count: a.value / s.count
              elif s.measure is MASS and item.each_weight: a.value * each_lb / s.measure_lb
  else None

contribution(a, item, p, orig, swapped):
  if swapped and a.kind is PACKAGES and orig and orig.size:
      for absolute in absolutize(a, orig.size):                 # count form first, then measure form
          if (c := direct(absolute, item, p)): return c
  if (c := direct(a, item, p)) and not (swapped and a.kind is PACKAGES): return c
  if swapped:                                                   # sizes not comparable: keep the same share
      share = a.value if a.kind is PACKAGES else share_of(direct(a, item, orig))
      if share is not None: return share of p (packages or lb) + {APPROX_SWAP}
  return unconverted(a, reason)                                 # SIZE_UNKNOWN | NEEDS_EACH_WEIGHT | NOT_CONVERTIBLE
```

**Each-weight** (`resolve_each_weight`, for count amounts on weight-sold or weight-sized items), first match wins:
1. The household's value.
2. For weight-sold items, `w = each_estimate / regular` (lb). Accepted only if 1/16 ≤ w ≤ 5 **and** the estimate differs from the regular price. Accepted values get the `EST_EACH_WEIGHT` flag ("est." badge).
3. Otherwise none, and the line has no price.

**Merge and round** (`build_list`):

```
for meal in meals; for dish in (main, *sides); for line in dish.lines:
    acc[line.item_id].add(line.amount.scaled(meal.scale), MealUse(meal.meal_id, dish.name))
for extra in extras with an item_id: acc[extra.item_id].extra += extra.quantity
per item:
  p = swaps.get(id, item.product); cs = [contribution(...)]
  pk, lb, ea = sums of cs; unconv = merge_by_kind_unit(c.unconverted)
  UNIT or unlinked: unit = PACKAGE; need = pk; plan_qty = max(ceil(pk), 1 if unconv else 0)
  WEIGHT:           w = resolve_each_weight(...); E = ceil(ea); M = ceil_to(lb, 1/4)
     if lb == 0 and no extra: unit = EACH;  need = ea;          plan_qty = E   # priced only when w is known
     else:                    unit = POUND; need = lb + ea*w;   plan_qty = M + E*w
                                            # w unknown and ea > 0 -> at_least, NEEDS_EACH_WEIGHT
  at_least |= bool(unconv)
  qty = plan_qty + extra
  override (same unit) -> qty = max(0, qty + delta)
     an EACH delta on a POUND line -> delta*w when w is known, else OVERRIDE_STALE (ignored)
  plan_bought = max(0, qty - extra)                              # extras are never leftovers
  leftover = None if have_it or at_least else plan_bought - need # < 0 -> SHORT
  leftover_measure = leftover in the package's measure unit and/or count
  used_by = meals de-duplicated, ordered by meal; dish names in line order
```

Unlinked items keep their raw amounts summed by kind and unit for display. Their quantity is the rounded-up sum when there's a single kind, otherwise "at least 1". A plain-text extra becomes its own line flagged `NO_PRODUCT`.

**Overrides are deltas.**
- The stepper shows the final quantity; the API stores `delta = typed − computed`.
- If the plan later needs more, the delta rides on top, so the list never silently under-buys.
- Product swaps exist for this trip only, or "Always use this", which re-links the item. Dishes are never edited.

**Pricing a line:**

```
have_it        -> shown; cost None; excluded from the total; not in the tally
p is None      -> NO_PRODUCT
p.price None or regular missing/0 -> NO_PRICE                    # a promo alone is not trusted
eff = promo if promo_valid else regular
promo_valid = regular > 0 and 0 < promo < regular
              and (promo_from is None or promo_from <= now) and (promo_until is None or now < promo_until)
              # a date-only expiration lasts through the end of that local day
PACKAGE: cost = qty * eff;  reg = qty * regular                   # exact integers
POUND / EACH: lbs = qty (POUND) or qty * w (EACH)
              cost = round_half_up(lbs * eff);  reg = round_half_up(lbs * regular)
savings = reg - cost
```

**Totals** (`summarize`) cover lines that have a cost and aren't have-it:

| Field | Value |
|---|---|
| `total` | Σ cost |
| `savings` | Σ savings |
| `not_priced` | Lines that aren't have-it and have no cost or are "at least" |
| `needs_check` | Lines flagged `APPROX_SWAP` |
| `prices_as_of` | The **oldest** `fetched_at` among priced lines |

The UI shows:
- "About $142"
- "$11 off on sale"
- "Prices as of 9:14 AM"
- "Before tax, fees and tip"
- "3 items have no price", when `not_priced` > 0

These are separate lines, not one string joined with dots.

**Recommendations** (`recommend`):

```
base = build_list(plan); B = lines by item_id
for (dish, meta) in candidates:
  skip unless it is a MAIN, not archived, and not already planned as a main
  hyp = build_list(plan.with_meal(Meal(dish, sides=(), scale=1)))  # a full rebuild: ~100 x 80 lines, trivial
  delta = hyp.total - base.total                                    # >= 0 (tested); clamped at 0 in production
  unpriced = lines this dish adds or increases that aren't fully priced (excluding have-it)
  shared: dish items i, in line order, with B[i].leftover > 0 and i not have-it:
      used  = min(H[i].need - B[i].need, B[i].leftover)             # each->lb via w if the unit changed
      value = used * B[i].unit_cents                                # 0 if unpriced
  skip if sum(value) < 100 cents       # rules out "only olive oil" and "nothing shared"
  named = top 3 by value with value >= 25 cents (or the single best), shown in the dish's line order
  more  = remaining nameable count
sort key: (unpriced > 0, about_dollars(delta), not favorite, last_made or date.min, delta, name.casefold(), dish_id)
return the first `limit`
```

- **Ties** are judged at the displayed-dollar level, so favorites, then meals not made recently, win among meals that "add about $4".
- Have-it items cost nothing in both totals. They are never named, and never count toward the threshold.
- **Copy:** `"{Name} uses your leftover {a, b and c[ and N more]}."` followed by one of:
  - "Nothing extra to buy." (adds 0)
  - "Adds less than $1." (rounds to $0)
  - "Adds about $N."
  - Append ", plus N item(s) without a price." when relevant.
- Lists use no serial comma.

### 8.5 Unit tests (fixtures for `tests/domain/`)

All cases use `now = 2026-10-06T14:00Z`; cents are integers.

| ID | Input | Expected |
|---|---|---|
| U1 | convert 1 lb → g; 1 cup → ml | 45359237/100000; 473176473/2000000 (exact) |
| U2 | 3 tsp vs 1 tbsp; 1 oz (weight) → fl oz | equal; DimensionMismatch |
| U3 | `dollars_to_cents(Decimal("1.15"))`, `"4.35"` | 115, 435 (`int(float*100)` gives 114, 434) |
| U4 | `round_half_up(897/2)`; `about_dollars(14150)`; `about_dollars(14149)` | 449 (`round` gives 448); 142; 141 |
| U5 | `q(0.5)` | TypeError |
| A1 | ¾ package of `16 oz` | 3/4 |
| A2 | 6 oz of `16 oz` | 3/8 |
| A3 | 1.5 lb of unit-sold `1 lb` | 3/2 → 2 packages; ½ lb left |
| A4 | 1.5 lb of weight-sold @549/lb | 3/2 lb; no package rounding; 824 |
| A5 | 2 cups of `64 fl oz` | 1/4 |
| A6 | 1 tbsp of `1 gal` | 1/256 → 1 package |
| A7 | 3 of `6 ct` | 1/2 |
| A8 | 2 cans, or 24 fl oz, of `12 x 12 fl oz` | 1/6 either way |
| A9 | 2 cups of `16 fl oz (473 mL)` | exactly 1 package (via 473 mL it would be 2) |
| A10 | 250 g of unit-sold `1 lb` | 25000000/45359237 → 1 |
| A11 | 1 cup of `16 oz` (weight) | InvalidAmount at entry |
| A12 | 3 onions; unit-sold `3 lb bag`; each-weight 8 oz | 1/2 → 1 bag |
| A13 | same as A12, no each-weight | at least 1; NEEDS_EACH_WEIGHT; tally +1 |
| A14 | 6 oz on an unparseable size | rejected at entry; at build time: at least 1, SIZE_UNKNOWN, shows "6 oz needed" |
| A15 | ½ package on an unparseable size | 1 package, priced |
| M1 | ¼ + ¼ + ½ package across 3 meals | 1 package (not 2), leftover 0 |
| M2 | 3 meals × 1.1 oz of `3.3 oz` | 1 package (floats give 2) |
| M3 | main ½ + side ½, same meal | 1 package; used_by lists the meal once with both dish names |
| M4 | same item twice in one dish (¼, ½) | 1 package, leftover ¼ |
| M5 | ×½ on 1 avocado (`1 each`) | 1 bought, ½ left |
| M6 | ×½ on ¾ package | 3/8 → 1 |
| M7 | 6 oz at ×2 plus 6 oz at ×1, of `16 oz` | 9/8 → 2; leftover 7/8 (14 oz) |
| M8 | M1 with meals and lines shuffled | identical list |
| W1 | 21 oz beef @549/lb | 3/2 lb → 824 |
| W2 | 1.5 lb thighs @299/lb | 449 |
| W3 | 3 onions; each-weight 8 oz; @149/lb | 1.5 lb → 224 |
| W4 | 3 onions; no each-weight; estimate $0.75 on $1.49/lb; valid promo $1.29 | each = 75/149 lb; 195; savings 30; EST_EACH_WEIGHT |
| W5 | estimate $0.0995 on $2.19/lb | each = 199/4380 lb < 1/16 → "3 onions, no price", tally +1 |
| W6 | estimate equals regular | rejected |
| W7 | 2½ onions (×½ of 5) + 4 oz; each-weight 8 oz | 1.5 + ¼ = 1.75 lb; ¼ lb left |
| W8 | 1 cup on a weight-sold item | rejected at entry; unconverted at build time |
| P1 | 2 packages; regular 349; promo 299 | cost 598; savings 100 |
| P2 | promo ended 2026-10-05T04:00Z | 698; savings 0 |
| P3 | `now == promo_until` | expired → regular |
| P4 | promo starts 2026-10-07 | regular |
| P5 | promo 349 (equal) / 400 (higher) / 0 / missing | regular; savings 0 |
| P6 | regular 0 or null; not sold at the store | NO_PRICE; not in total; tally +1 |
| P7 | regular null, promo 299 | NO_PRICE |
| L1 | unlinked item, 1 package | shown; NO_PRODUCT; tally +1 |
| L2 | have-it on a 499 line | shown; excluded from total; not in tally; leftover None |
| L3 | plain-text extra "birthday candles" ×1 | NO_PRODUCT line; tally +1 |
| L4 | item extra not in the plan, 2 × 129 | +258 |
| L5 | extra +1 on a planned item (need ¾) | qty 2; leftover ¼ (the extra isn't counted) |
| L6 | computed 1, user sets 3; the plan then needs 1¼ | delta +2 → 3, later 4 |
| L7 | override to 0 with need ¾ | qty 0; cost 0; SHORT |
| L8 | EACH override, unknown weight, line becomes POUND | OVERRIDE_STALE; override ignored |
| L9 | need 6 oz; original `8 oz` @250, swapped to `2 lb` @899 | 3/16 → 1 → 899; 13/8 lb left; dish unchanged |
| L10 | ½ package of `16 oz`, swapped to `32 oz` | 1/4 → 1 |
| L11 | ½ package with an unparseable original, swapped | ½ of the new package; APPROX_SWAP; needs_check +1 |
| L12 | 6 oz (weight) swapped to `6 ct` | 3/8 share → 1; APPROX_SWAP |
| L13 | ½ of unit-sold `3 lb bag`, swapped to loose @149/lb | 1.5 lb → 224 |
| L14 | lines P1 + L9 + L13 + a have-it line + a no-price line | total 1721; savings 100; regular 1821; not_priced 1 |
| L15 | headline for 14150 at 9:14 AM | "about $142 … prices as of 9:14 AM … excludes tax, fees and tip" |
| L16 | priced lines fetched at 9:14 and 11:02 | prices_as_of = 9:14 |
| L17 | snapshot, then prices change | snapshot unchanged; exact round-trip |

**Recommendation fixture: base plan "Taco night"** (total 1676)

| Item | Package | Price | Taco night uses |
|---|---|---|---|
| Lettuce | `1 ct` | 199 | ½ |
| Cheese | `8 oz` | 250 | 4 oz |
| Beef | `2 lb` | 998 | 1 lb |
| Shells | `12 ct` | 229 | 12 |

| ID | Case | Expected |
|---|---|---|
| R1 | "Taco salad": same lettuce, cheese and beef + 2 tomatoes (`each` @69) + chips 1 pkg @250 | adds 388; values 99.5, 125, 499; "Taco salad uses your leftover lettuce, cheese and ground beef. Adds about $4." |
| R2 | candidate shares nothing | hidden |
| R3 | only 2 tbsp of a `16.9 fl oz` oil @899 | value ≈ 53 < 100 → hidden |
| R4 | fully covered by leftovers | "… Nothing extra to buy." |
| R5 | adds 40 | "Adds less than $1." |
| R6 | includes a new unlinked item | ranked after all fully priced meals; "Adds about $3, plus 1 item without a price." |
| R7 | A: 412, favorite; B: 388. C (last made 2026-08-01) and D (never), both about $4, not favorites | A before B; D before C |
| R8 | planned, archived and side dishes | excluded |
| R9 | 5 nameable shared items | names the top 3, then "and 2 more" |
| R10 | cheese leftover ½; candidate needs 8 oz | buys 1 more; cheese named (value 125) |

### 8.6 Property tests (Hypothesis, `tests/domain/strategies.py`)

Strategies draw from a pool of about 5 items (so merging is forced), `st.fractions(max_denominator=64)`, and cents from 1 to 5000. A deliberately naive reference implementation cross-checks plans that only have unit-sold items.

1. `parse_size` never raises on `st.text()`, and `parse(format(s)) == s`.
2. Converting to a unit and back gives back the identical value; converting across dimensions always raises.
3. Rounding never under-buys: with no override, `qty ≥ need` and `qty − need` < one step (1 package, 1 piece or ¼ lb).
4. Merging is order-independent: shuffled meals and lines give the same output.
5. Merged packages ≤ the sum of per-meal packages, and ≥ the largest single-meal value.
6. Adding a meal never decreases any line's quantity, the total, or `not_priced` (with overrides fixed).
7. `0 ≤ marginal_cost == total(plan + m) − total(plan)`.
8. `need(×2) == 2·need(×1)`, and `scaled(2).scaled(1/2) == scaled(1)`.
9. `total ≥ 0`, `savings ≥ 0`, and `total + savings == regular_total`. Marking have-it never raises the total; raising a regular price never lowers it.
10. Effective price ≤ regular, and the promo is used exactly when `promo_valid`.
11. Swapping to an identical product changes nothing except adding `SWAPPED`; a delta of 0 is a no-op.
12. `|round_half_up(x) − x| ≤ ½`.
13. `recommend` is deterministic under shuffled candidates; returns at most `limit`; every result names ≥ 1 item and meets the value threshold.
14. Every public constructor rejects floats.

### 8.7 What the amount picker offers

`amount_options` decides this; the UI never offers something the math can't convert.

| Package | Offers |
|---|---|
| Unit-sold, weight size (`16 oz`) | Parts of the package (¼ steps: ¼ ½ ¾ 1 2); weight in oz/lb/g/kg; counts only once an each-weight is set |
| Unit-sold, volume size (`64 fl oz`) | Parts; kitchen measures (tsp, tbsp, ¼/½/1 cup presets, fl oz) |
| Count or each (`6 ct`, `each`) | Count in ½ steps; package |
| Multipack (`12 x 12 fl oz`) | Count (cans); the inner measure; package |
| Sold by weight (per lb) | Weight (½ lb, 1 lb presets) and count. For counts, ask "About how much does one weigh?" once: Small 4 oz / Medium 8 oz / Large 12 oz / 1 lb / Other, pre-filled from a sane Kroger estimate |
| Unparseable size | Package parts only, plus "Fix size" |

- **Live preview:** "About 3/8 of the 16 oz package, about $0.94". Counts in packs of several read in pieces: "2 of the 12", "All 12", "15 (about 1 1/4 boxes of 12)".
- **Size corrections:** if a correction changes a size's dimension, the affected dish lines get a "check amount" flag.
- **On the list:** the stepper shows the final quantity, with a "you added 2" chip. Short and approximate lines get visible chips.

### 8.8 Defaults adopted

The owner can overrule any of these.
1. Overrides are stored as deltas, never as pinned absolute numbers.
2. Weight-sold items round to whole pieces plus ¼ lb steps.
3. Kroger's per-each estimate is a fallback, limited to 1 oz–5 lb, with an "est." badge.
4. Promo dates are half-open instants; a date-only expiration lasts through the end of that local day.
5. Extras never count as leftovers. Have-it covers the whole line; adding an extra clears have-it.
6. Recommendations: show 3; require ≥ $1 of leftover value; only name items worth ≥ 25¢; rank by the displayed dollars so favorites can break ties; meals with unpriced items go last.
7. Swap fallback: when sizes can't be compared, buy the same share and flag "check amount".
8. "oz" always means weight, and "pt" a liquid pint. The household corrects juice sold as "64 oz" and berries sold by the dry pint.
9. If two items link to the same product, flag it; don't auto-merge.

---

## 9. Live updates and offline shopping

ADR 0014 covers live updates and ADR 0015 covers offline sync. The goal: two people can shop one trip on two phones, with or without signal, and never see an error wall.

### 9.1 Data flow

```
PHONE A (member m_1)                    SERVER (one process)                       PHONE B
1 open the trip → GET /api/trips/t_42 ─▶ snapshot + states (version 180)
  store in IndexedDB; the service worker caches the trip's photos;
  wake lock on; card: "Ready for the store"
2 [no signal] tap Milk
  one IndexedDB transaction: outbox.add(item.set_state=done, ts=now+offset)
  screen = server state ⊕ pending ops → Milk moves to Done, "19 of 31"
  flush fails → server unreachable → pill "Offline · saved on this phone"
3 [signal back] flush (stream opens | online | app visible | 15 s timer | app start)
  POST /api/trips/t_42/ops {known_version:180, ops:[…]} ─▶ write lock; BEGIN
                                            skip op_ids already seen; last writer wins
                                            item.version = trip.version = 181
                                            INSERT applied_ops; COMMIT
                                            hub.publish(trip.items v181) while still holding the lock
  ◀── {results:[applied], items:[changed since 180], trip_version:181}
  remove ops from the outbox; merge; the pill clears
                                            hub → every connection queue ──────▶ trip.items (181 > 180) → merge
                                                                                 "Milk · by Mia"  (p95 < 2 s)
4 A phone that was offline reconnects with /api/events?since=<epoch>:<seq>
  → hello{mode:replay} + the missed frames, or hello{mode:resync} → refetch, plus trip deltas
```

### 9.2 Trip ops API

**Reading**
- `GET /api/trips/{id}` returns the whole trip.
- `GET /api/trips/{id}?since_version=N` returns the header plus only the items whose version is greater than N.

**Writing:** `POST /api/trips/{trip_id}/ops`, with at most 100 ops and 64 KB per batch (small enough for a `keepalive` request).

```json
{ "client_id": "c-5b1e…", "known_version": 180,
  "ops": [{ "op_id": "0b6f2c1e-…", "v": 1, "kind": "item.set_state", "item_id": "…",
            "state": "done", "client_ts": 1791306000000, "client_seq": 412 }] }
```

- **Kinds:**
  - `item.set_state` (`todo` | `done` | `missed`)
  - `item.set_note` (≤ 200 characters, or `null` to clear)
  - `trip.finish` (optional `actual_total_cents`)
  - `trip.reopen`
- **Ops carry absolute values, never toggles,** so replaying or reordering them is harmless.
- **Op versions:** `v` is the op schema version. The server keeps accepting every version ever shipped, because an offline phone may be running an old build.
- **The member comes from the session's device.** Shopping mode asks for the one-tap member pick first if the device has none.

**Conflict rule: last writer wins per item field, using corrected client time.** State and note are separate fields; trip status is a third.

Why not plain server-arrival order? Suppose phone A checks Milk offline at 17:00, phone B marks Milk "couldn't find" online at 17:05, and phone A syncs at 17:20. Arrival order would let the older action win. Corrected client time keeps B's.

1. **Clock offset.** Every API response carries `X-Server-Time-Ms`.
   - The client estimates `offset = server − (t_send + t_recv)/2`.
   - It keeps the lowest-latency sample of the last 8 and persists it.
2. **Stamping.** `client_ts = max(Date.now() + offset, lastIssued + 1)`, so a device's timestamps always increase. An Undo always beats the action it undoes.
3. **Server clamp.** `effective_ts = min(client_ts, received_at)`, so a phone with a fast clock can't claim the future. For ops sent while online, this reduces to arrival order.
4. **Apply** if `effective_ts ≥ register_ts`.
   - Ties go to the later arrival.
   - Within a batch, ops apply in `client_seq` order.
   - The server alone decides. Clients display server state with their own pending ops laid on top.
5. **Measure it.** Log `client_ts − received_at` for online ops, to see how much clock skew real phones have.

**Response:** always 200 once the batch has been parsed.

```json
{ "trip_id":"t_42", "trip_version":183, "trip_status":"active", "server_time":1791306001123,
  "results":[{"op_id":"…","status":"applied"},{"op_id":"…","status":"superseded"},
             {"op_id":"…","status":"duplicate","original":"applied"},
             {"op_id":"…","status":"rejected","reason":"trip_closed"}],
  "items":[ /* every item with version > known_version */ ], "trip":{ /* header if it changed */ } }
```

- **Duplicates:** a repeated `op_id` is never applied twice. The server checks it first and returns the original result.
- **Client:** removes every op that comes back with any of the four statuses.
- **Other responses:**

  | Response | Client action |
  |---|---|
  | 401 | Keep the ops; mark sign-in expired |
  | 404 | Drop the trip and its ops |
  | 413 | Split the batch and resend |
  | 422 | Move the ops to a dead-letter store (a client bug); keep the rest flowing |
  | 5xx, network error, or a non-JSON reply | Keep the ops; back off 1 → 2 → 5 → 10 → 30 s with jitter |

- **Events:** each applied batch publishes one `trip.items` event, plus `trip.state` if the header changed. An all-duplicate or all-superseded batch publishes nothing.

**Undo** (a 6-second toast) queues a new `item.set_state` back to the previous state.
- **Not yet sent:** outbox compaction deletes the original op, so only the final intent is sent.
- **Already sent:** the always-increasing timestamp guarantees the undo wins.

**A trip finished on another phone**
- Item ops are still applied (without reopening the trip) up to 24 h after `finished_at`, because someone offline really did put those items in the cart. After that they come back `rejected: trip_closed`.
- When a response says the trip is finished, the phone leaves shopping mode with a calm sheet: "Mia finished this trip · your 3 check-offs were saved" [Done] [Reopen].

**Finishing while offline**
- `trip.finish` is just another op. Locally the trip moves to History with a small "will sync" mark, the wake lock is released, and shopping mode closes.
- On the server, status is last-writer-wins on `status_ts`:
  - Finishing an already finished trip returns `superseded`, but fills in `actual_total_cents` if it was empty.
  - Between a finish and a reopen, the later one wins.
- "Shop this again", which re-prices from Kroger, and all planning edits need a connection.

### 9.3 Server-sent events

**Stream shape**
- One household-wide stream per app instance: `GET /api/events?since=<epoch>:<seq>`. No per-trip streams, which would add connections and churn on every screen change.
- Every frame's `data:` is JSON with a `type`.

| type | Payload | Client action |
|---|---|---|
| `hello` | epoch, seq, mode (`live`/`replay`/`resync`), server_time | Take a clock sample. On `resync`: invalidate all queries and fetch deltas for active trips |
| `ping` (every 15 s, no `id`) | t | Reset the watchdog; feed the buffering detector |
| `trip.items` | trip_id, trip_version, by, items[] | Merge into the cache and IndexedDB if the version is newer |
| `trip.state` | status, version, finished_at/by, actual_total_cents | Patch the header; invalidate the active and history lists; show the "finished by" sheet |
| `trip.created`, `trip.deleted` | trip_id | Download the trip and its photos / remove it locally |
| `plan.changed`, `list.changed`, `extras.changed`, `settings.changed`, `members.changed` | id, version, by | Debounced invalidation (250 ms, at most 1 s); skip if the cached version is already this new |
| `session.expired` | — | Mark sign-in expired; stop the stream; keep the outbox |

- **Trip events carry the change itself,** because they are small, frequent and needed while shopping.
- **Planning events only trigger a refetch,** because the server computes the totals.

**Resuming after a disconnect.** Two kinds of numbering, for different jobs:
- **Per-entity `version`** (stored in the DB): HTTP responses and events can arrive in either order and still merge correctly.
- **`epoch:seq`** (in memory): `epoch` is random per server start and `seq` has no gaps, so the client can detect a missed event.

On connect, the server:
1. registers the new connection's queue;
2. reads the ring buffer of the last 1024 frames, de-duplicating anything already queued;
3. if `since` has the same epoch and falls inside the ring, replays the missed frames; otherwise sends `resync`.

The reconnecting wrapper creates a new EventSource, and a new EventSource doesn't send `Last-Event-ID`. So the client passes `?since=`, and the server takes the larger of the two. A seq that isn't `last + 1` makes the client reconnect from its last good position.

**Headers.** `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`.
- Not sent: `Content-Length`, `Content-Encoding`, or a manual `Connection` header.
- The first bytes are `retry: 3000` followed by `hello`.
- No app-level gzip anywhere (it breaks flushing). Compression belongs at the proxy, which must exclude this route.

**Heartbeat and proxies**
- The `ping` goes out every 15 s, inside both Cloudflare's 100 s and nginx's default 60 s read timeouts.
- It's a real data event, because comment-line pings never reach JavaScript.
- The client watchdog reconnects after 40 s with no frame, which catches dead mobile connections that still look open.

| Proxy | What can go wrong | Fix (documented in `docs/DEPLOY.md`) |
|---|---|---|
| nginx / Nginx Proxy Manager | Buffering; HTTP/1.0 to the upstream | It honors `X-Accel-Buffering: no`. Belt and braces, add a location for `/api/events`: `proxy_http_version 1.1; proxy_set_header Connection ""; proxy_buffering off; gzip off;` |
| Traefik | `buffering` and `compress` middlewares | Don't attach `buffering`; add `excludedContentTypes: text/event-stream` to `compress` |
| Caddy | `encode` compressing `text/*` | `@notsse not path /api/events` then `encode @notsse zstd gzip` |
| Cloudflare | Compression or caching | `no-transform`; a Cache Rule that bypasses `/api/*` |

- **Buffering detector:** the client treats a `hello` that arrives more than 5 s late, pings that arrive in bursts, or three failed opens in 60 s (while normal requests work) as a buffering proxy. It then quietly switches to polling:
  - the active trip's delta every 5 s while shopping;
  - planning screens every 30 s;
  - another stream attempt every 60 s.
- Only Settings → Connection shows that this happened.

**Connection limits and auth**
- HTTP/1.1 allows 6 connections per origin, shared by all tabs. Turn on HTTP/2 at the proxy.
- The client closes the stream on `visibilitychange: hidden` and `pagehide`, and reopens with `since` on visible or `pageshow`. iOS drops it on lock anyway.
- The stream is authenticated by the session cookie; an invalid session gets 401 before streaming starts.
- EventSource can't see status codes, so when it closes the wrapper probes `GET /api/auth/session`:
  - 401 → sign-in expired; stop retrying;
  - network error → offline; keep backing off;
  - 200 → reconnect.
- Each heartbeat checks an in-memory list of revoked sessions. A revoked session gets `session.expired`, and the stream ends.

**Single-worker invariant** (ADR 0002, repeated in CLAUDE.md). Exactly one process serves the API: uvicorn `--workers 1`, one replica, no gunicorn, data on local disk.
- **What lives only in that process:** the event hub (sequence numbers, ring buffer, connections), the write lock, the SSE fan-out and the login rate limiter.
- **How it's enforced:**
  - Startup takes `flock(LOCK_EX|LOCK_NB)` on `/data/.lock` and exits clearly if another process holds it.
  - Shutdown sets `hub.closing`, which ends the streams, so `timeout_graceful_shutdown` isn't held up.
  - One `asyncio.Lock` serializes DB writes, which use `BEGIN IMMEDIATE`.
  - Events are published after commit while still holding the lock, so stream order equals commit order.

### 9.4 Client architecture

**Modules** (`frontend/src/lib/`)

| Module | Job |
|---|---|
| `api` client | 10 s timeout; treats non-JSON as unreachable; reports to the connection store; takes clock samples |
| `clock.ts` | Clock offset and always-increasing timestamps |
| `db.ts` | IndexedDB |
| `outbox.ts` | Pending ops, compaction, flush |
| `connection.ts` | Connection status |
| `events.ts` | Reconnecting EventSource with backoff from 500 ms to 5 s plus jitter, `since`, watchdog, session probe, close when hidden |
| `eventRouter.ts` | Turns events into cache updates |
| `keys.ts` | The query-key factory |
| `wakeLock.ts` | Keeps the screen on |
| `images.ts` | Talks to the service worker about trip photos |

**Two local stores, on purpose**

1. **`db.ts`** (`idb`, with versioned `upgrade()` migrations; never wiped by an app update):
   - stores `trips` (active trips plus trips finished in the last 24 h), `outbox`, `deadletter` and `meta` (client ID, member, clock offset, last `epoch:seq`, last successful sign-in, which photos belong to which trip);
   - every call reopens the database once on `UnknownError` or `InvalidStateError`, because iOS can drop IndexedDB connections after backgrounding.
2. **TanStack Query persister** (`PersistQueryClientProvider` with an async persister over `idb-keyval`, in a separate database):
   - planning data for **offline reading only**: queries marked `meta.persist` (me, members, current plan, current list, extras, active trips);
   - `maxAge` 7 days; `buster` is a schema constant.

Trips are deliberately kept out of the TanStack store:
- The persister throws everything away when `buster` or `maxAge` doesn't match.
- It writes one throttled blob of the whole cache.
- iOS can kill the app mid-trip and relaunch it on a newer service worker.

Kroger search results are never stored on the device, and neither is history.

When the app starts or becomes visible, it downloads every active trip into IndexedDB and caches its photos. A phone is ready even when someone else created the trip.

**Outbox**
- **Enqueue** is one IndexedDB transaction: delete any pending op with the same (trip, item, kind) that isn't currently being sent, then write the new op. A 300 ms debounce groups rapid taps.
- **Flush:**
  - one at a time; oldest first, one trip at a time;
  - "being sent" is tracked in memory only, so a crash resends and gets `duplicate`.
- **Flush triggers:**
  - a new op;
  - the `online` event;
  - the app becoming visible;
  - `pageshow`;
  - the stream opening;
  - app start;
  - every 15 s while ops are pending and the app is visible;
  - backoff timers.
- **On `hidden`/`pagehide`:** a best-effort `fetch(…, {keepalive: true})`. There's no Background Sync, because Safari and iOS don't support it.
- **What the screen shows:** `useTripView(id)` passes the server-confirmed trip query and the pending ops (`useSyncExternalStore`) to a pure `deriveView(trip, pending)`. It returns:
  - the groups (sections in walking order, then aisle and side; Done collapsed; Couldn't find last);
  - the "18 of 31" progress;
  - the running total of checked items.
- **Rollback is automatic:** when an op leaves the outbox, its overlay disappears.

**Planning screens write only while online** (they are not queued).
- **Why:** their edits depend on the server (pricing, merging, deletes), where last-writer-wins isn't enough, and they usually happen at home on Wi-Fi.
- **Online:** optimistic updates.
  - `onMutate`: cancel, snapshot, set.
  - `onError`: roll back.
  - `onSettled`: invalidate only when this is the last pending mutation for that key.
  - `retry: 0`.
- **Errors:**
  - A network failure rolls back with the toast "Not saved — you're offline".
  - A 409 rolls back, refetches, and says "Mia just changed this".
- **Offline:** planning screens are readable from the stored copy, labelled "Updated 2 h ago". Edit controls are disabled, with one inline line saying why; never a modal.
- **Later:** the first candidate for queueing is "add extra", because it only appends.

**Connection status**

The store tracks:
- `network`: the `navigator.onLine` hint only;
- `server`: reachable, unreachable or unknown, based on real request results;
- `stream`;
- `auth`;
- `pending`;
- `lastSyncAt`.

TanStack's `onlineManager` follows `server === reachable`, so queries pause instead of erroring. While unreachable and visible, the client probes `GET /api/health` every 15 s.

What the user sees:

| State | Shown |
|---|---|
| Synced | Nothing |
| Unreachable for 3 s or more | "Offline · saved on this phone" |
| Ops pending while reachable | "Syncing 3…" |
| Sign-in expired | "Sign in to sync" (tappable) |

The indicator is `role="status"` with polite announcements.

Other rules:
- A device that has signed in before is treated as signed in while offline; only a real 401 signs it out.
- Route loaders read local data and never throw on a network failure.
- A trip that has never been opened on this phone, opened while offline, shows: "Open this trip once with signal to save it on this phone".

**Query keys**

```ts
export const qk = {
  me: () => ['me'] as const, members: () => ['members'] as const,
  plan: { all: () => ['plan'] as const, current: () => ['plan', 'current'] as const },
  list: { all: () => ['list'] as const, current: () => ['list', 'current'] as const },
  extras: () => ['extras'] as const, settings: () => ['settings'] as const,
  trips: { all: () => ['trips'] as const, active: () => ['trips', 'active'] as const,
    history: (cursor: string | null) => ['trips', 'history', cursor] as const,
    detail: (id: string) => ['trips', 'detail', id] as const },
};
```

**Events into the cache**
- Trip events → `setQueryData` when the version is newer; skip trips that aren't cached; also write to IndexedDB.
- Everything else → the key goes into a set, and the set is invalidated on a trailing 250 ms debounce (1 s at most). The invalidation waits while a mutation on that key is in flight.
- `resync` → `invalidateQueries()` plus trip deltas.

### 9.5 PWA and service worker

vite-plugin-pwa runs with `strategies: 'injectManifest'`, `srcDir: 'src'`, `filename: 'sw.ts'`, `registerType: 'prompt'`, `injectRegister: false` (no inline script, which keeps the CSP strict) and `devOptions.enabled: false`.

```ts
precacheAndRoute(self.__WB_MANIFEST); cleanupOutdatedCaches(); clientsClaim();
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//] }));
const img = new CacheFirst({ cacheName: 'kroger-img-v1', matchOptions: { ignoreVary: true },
  fetchOptions: { credentials: 'omit' },
  plugins: [ new CacheableResponsePlugin({ statuses: IMG_CORS ? [200] : [0, 200] }),
             new ExpirationPlugin({ maxEntries: 150, maxAgeSeconds: 3 * 86400, purgeOnQuotaError: true }) ] });
registerRoute(({ url, request }) => request.destination === 'image'
  && IMAGE_ORIGINS.includes(url.origin) && url.pathname.startsWith('/product/images/'), img);
// Deliberately NO /api route and no default handler: /api/* and /api/events are never intercepted or cached
// (cookie-authenticated data would outlive sign-out; IndexedDB is the offline layer).
```

**Messages**
- `SKIP_WAITING`.
- `TRIP_IMAGES_WARM {tripId, urls}`:
  - fetches 4 at a time through the image strategy, under `waitUntil`;
  - posts progress back on a MessagePort.
- `TRIP_IMAGES_RELEASE {tripId}`: deletes photos not used by another active trip.

**Kroger photos on the device**
- **Why the service worker caches them** instead of leaving them to the browser's HTTP cache: shopping offline needs the photos, and the browser's cache isn't reliable offline.
- **Kroger terms:** a fixed 3-day maximum, plus deleting a trip's photos when it finishes, is the conservative way to honor the cache rule.
- **Opaque (no-CORS) responses** count heavily against storage quota. That's why there's an entry cap, `purgeOnQuotaError` (giving up photos protects the trip data), and release on finish.
- **CORS (unverified until M3):**
  - If Kroger's image host sends `Access-Control-Allow-Origin`, add `crossorigin="anonymous"` to every product `<img>` and cache only 200s.
  - Also honor the image's own `max-age`.
- **Broken cached images:**
  1. On `<img>` error, delete that URL from the cache.
  2. Retry once when reachable.
  3. Otherwise show a placeholder with the product name.
- **Size and rendering:**
  - `medium` images in list rows; `large` only on tap, online, and never pre-cached.
  - `object-fit: contain` in a padded white square; the box is rounded, never the image. No filters or opacity on the image; Done rows dim only the text.
  - `referrerpolicy="no-referrer"` until hot-link behavior is tested.
- **CSP:** the page allows `img-src https://www.kroger.com/product/images/`. The `/sw.js` response alone adds `connect-src https://www.kroger.com`, so the worker can pre-fetch.

**"Get ready for the store"**
- An automatic card when a trip opens, with four checks:
  1. trip saved on this phone;
  2. photos saved (31/31);
  3. app works offline (`serviceWorker.controller` set and `caches.match('/index.html')` succeeds);
  4. `navigator.storage.persist()` requested.
- It ends on **Ready for the store**, the only state the user needs to read.

**Updates**
- **Prompt, never auto-update.** `useRegisterSW` checks `r.update()` whenever the app becomes visible and every hour.
- The "New version · Refresh" pill shows only outside shopping mode and only when the outbox is empty. Refresh runs `await outbox.flush()`, then `updateServiceWorker(true)`.
- The SPA compares its build version (`__APP_VERSION__`) with `/api/version` when focused and every 15 minutes.
- It reloads on `vite:preloadError`, because old chunks 404 after a deploy.
- An OS kill can still activate a waiting worker mid-trip. IndexedDB migrations and the server accepting old op versions cover that.

**Manifest**
- name "Dinner Bell", short name "Dinner Bell", `display: standalone`, theme and background from the tokens.
- Icons at 192 and 512 px plus a maskable one, an apple-touch-icon, and iOS splash images generated at build time.

### 9.6 iOS and Android specifics

| Topic | Behaviour (confidence) | Design response |
|---|---|---|
| Installed iOS web app storage | Its own cookies, IndexedDB and service worker, separate from Safari (high) | In a normal Safari tab on iPhone, show the install guide **before** the password step (with "Continue in Safari" available). The member pick is stored on the server per device |
| Installing | iOS: Share → Add to Home Screen; iOS 26 may default "Open as Web App" on (medium). `beforeinstallprompt` is Chromium-only (high) | Detect `display-mode: standalone`. Chromium gets an Install button; elsewhere an illustrated guide |
| Screen Wake Lock | Chrome Android 84+, Safari 16.4+, Firefox 126+ (high); broken in iOS installed apps before 18.4 (medium) | §9.7; real-device checklist |
| Storage eviction | Safari tabs lose script storage after 7 days of Safari use without visiting the site; installed apps are exempt (high) | Encourage installing; `persist()`; the server is the source of truth; flush promptly |
| EventSource in the background | iOS suspends the page; the connection drops and may look open on return (high) | Close when hidden; reopen, flush and fetch deltas when visible; 40 s watchdog |
| `navigator.onLine` | `false` is reliable; `true` is not, e.g. on store Wi-Fi login pages (high) | Status comes from real requests |
| Background Sync and push | Not available on iOS (high) | Flush in the foreground only; no push |
| IndexedDB on iOS | Can lose its connection after backgrounding (medium) | Reopen wrapper in `db.ts` |

### 9.7 Wake lock

- `lib/wakeLock.ts` plus a `useKeepAwake(active)` hook, with state in an external store so tests can inject fakes.
- **Turning it on:** `enable()` runs from the **Start shopping** tap, since a user gesture helps on Safari. It requests the lock if the page is visible, with one request in flight at a most.
- **Keeping it:**
  - On `release`, clear the reference.
  - On becoming visible, request it again.
  - A request that resolves after the page went hidden is dropped.
- **If refused:** a `NotAllowedError`, such as from battery saver, sets `denied` and retries once on the next tap.
- **Turning it off:** `disable()` runs when leaving shopping mode, finishing the trip, or seeing the "finished by someone else" sheet.
- **UI:** a small "Screen stays on" note in the shopping header. When unsupported or denied, a one-time dismissible tip:
  - iPhone: "Your screen may dim while you shop. Settings → Display & Brightness → Auto-Lock".
  - Android: "Display → Screen timeout".
  - No hidden-video trick.

### 9.8 Tests for this layer

**Playwright** (`frontend/e2e/`)

Projects:
- `mobile-webkit`: the iPhone preset with the viewport overridden to 390×844.
- `mobile-chromium`: 390×844.
- `desktop-chromium`: 1440×900.

Setup:
- Runs against the production build served by the real backend (`dinnerbell serve`, fake Kroger, temp `DATA_DIR`, `DINNERBELL_TEST_MODE=1`).
- Seeded photos come from a local fixture server via `IMAGE_ORIGINS`.
- A global fixture fails a test on any `alertdialog`, browser dialog, uncaught page error or CSP violation (the "no error wall" guard).
- Service-worker tests run on Chromium only, after waiting for `serviceWorker.ready` and a reload. WebKit runs the app-level offline tests with service workers blocked.

Scenarios:
1. **Offline check-off:**
   1. Wait for "Ready for the store", then go offline.
   2. Check three items; mark one missed with a note.
   3. Assert "3 of 31", the running total, the offline pill, and no dialogs.
   4. On Chromium, a reload while offline still works.
   5. Back online: the server state, including who did each check-off, matches.
2. **Live sync:** two browser contexts, A and B. A's check-off shows on B within 3 s, and the reverse. Planning edits sync on desktop.
3. **Conflicts:**
   - A checks Milk offline, then B marks it missed. After A reconnects, Milk is "missed".
   - A's clock is set 10 minutes fast via `page.clock`. The clamp keeps B's later action.
4. **Undo** works online and offline. A request count proves compaction sent only one op.
5. **Missed:** retrying returns the item to `todo` and keeps the note.
6. **Finish:**
   - With a total: the trip appears in History on both phones.
   - Reopen works.
   - Shop this again works online; offline it is disabled with a gentle message.
7. **Finish while offline:** syncs on reconnect.
8. **Late ops:** A makes 2 offline check-offs while B finishes. A reconnects: the ops are applied, and A shows the "finished by" sheet.
9. **Dropped streams** during edits lose nothing (replay). A backend restart takes the resync path.
10. **Revoked session:** "Sign in to sync" appears, the outbox is kept, and it flushes after sign-in.
11. **Wake lock** (a fake injected with `addInitScript`): requested on enter, requested again after a visibility change, released on finish.
12. **Update prompt:** with two builds, the prompt never appears inside shopping mode.

**Vitest** with `fake-indexeddb/auto` and injected dependencies:
- Outbox:
  - compaction never touches ops in flight;
  - batches split when too large;
  - every response status and HTTP code is handled;
  - the backoff schedule follows fake timers;
  - rejected ops go to the dead-letter store.
- `deriveView` and version merging.
- Clock offset and always-increasing timestamps.
- Stream gap detection.
- The debounced invalidator.
- The wake-lock state machine.
- Connection-status transitions.
- An IndexedDB migration from v1 to v2.

**pytest:**
- **Duplicates:** the same `op_id` twice causes one change and returns the original result.
- **Last-writer-wins:**
  - an older op is superseded;
  - a tie goes to the later arrival;
  - a future timestamp is clamped;
  - state and note are independent.
- **Batches and versions:**
  - a batch applies in order;
  - an unknown item or member is rejected while the rest applies;
  - versions have no gaps;
  - `since_version` deltas are correct.
- **Finished trips:**
  - the 24 h window;
  - finish vs. reopen ordering;
  - finishing fills an empty total.
- **Events:** exactly one per applied batch, published after commit.

**SSE tests**
- `httpx.ASGITransport` waits for the whole response, so it can't read an endless stream. The SSE tests use a small hand-written ASGI harness instead: `send` goes to a queue, and `receive` returns the request, then waits for a test-triggered `http.disconnect`.
- They assert:
  - the headers;
  - `retry` and `hello` come first;
  - published events arrive as frames;
  - pings arrive (heartbeat set to 50 ms);
  - replay and resync behave by `since`;
  - an overflow causes `resync`;
  - a request without a session gets 401;
  - a revoked session gets `session.expired`;
  - the listener count returns to 0 after disconnect.
- Plus one smoke test against a real uvicorn on `127.0.0.1:0`, and a manual `just proxy-matrix` that streams through nginx, Caddy and Traefik in Docker and asserts events arrive less than 1 s apart.

**Manual check before each release:** a real store run in airplane mode on an installed iPhone and an Android phone (the deploy report includes it).

---

## 10. Access, login and security

### 10.1 Access

ADR 0003 covers this.
- Phones reach the app over HTTPS on a subdomain of the owner's existing reverse proxy, which works on cellular.
- Installing to the home screen, the service worker and the wake lock all require HTTPS.
- The app never relies on the proxy for authentication: the repo is public and others may deploy it without one.
- `TRUSTED_PROXIES` lists the proxy's IPs or CIDRs; uvicorn trusts forwarded headers only from those. The signed-in diagnostics page shows the resolved client IP and the raw `X-Forwarded-For` and `X-Forwarded-Proto`, so the owner can set it correctly from a phone.
- Turn on HTTP/2 at the proxy. The per-proxy SSE settings are in §9.3.

### 10.2 Password, sessions and devices

ADR 0004 covers this.
- **The password** is `APP_PASSWORD` from env, 12+ characters (a passphrase).
  - Env-only config means there's no first-visitor race to set a password on a public URL.
  - Login compares the SHA-256 of the given and configured passwords with `hmac.compare_digest`. No password hash is stored.
- **Rotating the password signs everyone out.**
  - `app_meta.password_fp = HMAC(k_pwfp, password)`.
  - If it changes at boot, `auth_epoch` increments, and every session dies.
  - Settings also offers **Sign out all devices** (an epoch bump) and per-device revoke.
- **Keys:** HKDF-SHA256 subkeys from `APP_SECRET_KEY` (32+ characters), with info strings `session-v1`, `kroger-tokens-v1`, `password-fp-v1` and `key-check-v1`.
- **Session cookie:**
  - Named `__Host-dinnerbell`; plain `dinnerbell` on http localhost, for tests only.
  - Value `v1.<device_id>.<epoch>.<mac128>`. It's valid only when the MAC verifies, the device isn't revoked, and the epoch matches.
  - Attributes `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=31536000` (under Chrome's 400-day cap). Re-issued when older than 30 days, so phones in use never expire.
  - HttpOnly server cookies aren't subject to Safari's 7-day script-storage cap.
- **Devices** are `devices(id, label, member_id, created_at, last_seen_at, revoked_at)`.
  - "Who's using this?" is stored with `PUT /api/auth/member`, so attribution comes from the device row.
  - Settings lists devices with **Sign out other devices**.
- **QR join** (M5):
  - A signed-in phone shows a QR code for `/join#<token>`: a single-use, 5-minute token stored hashed.
  - The new phone signs in without typing the password.

### 10.3 CSRF

- The session cookie is `SameSite=Lax`.
- Every mutating `/api` request must carry `X-Dinner-Bell: 1`. The app serves no CORS, so other sites can't add that header.
- When `Origin` is present it must equal `APP_BASE_URL`; `Origin: null` is rejected.
- `Referrer-Policy: same-origin`. With `no-referrer`, browsers send `Origin: null` on same-origin POSTs.

### 10.4 Login rate limiting

- **Keyed on the client IP as uvicorn resolves it:** the rightmost untrusted `X-Forwarded-For` hop, only when the peer is in `TRUSTED_PROXIES`.
- **Per IP:** 5 failures per 15 minutes, then 429 with `Retry-After`.
- **Globally:** 50 failures per hour pauses logins for 15 minutes. Already signed-in phones are unaffected.
- **Kept in memory.** That's enough:
  - the single process is guaranteed (§9.3);
  - an attacker can't trigger restarts;
  - a reset only restores 5 tries against a 12+ character passphrase.
- **UI messages:**
  - "That password didn't match. Try again."
  - "Too many tries. Wait 10 minutes."

### 10.5 Security headers

- **CSP:** `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob: https://www.kroger.com/product/images/; font-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'`.
  - `/sw.js` adds `connect-src https://www.kroger.com` (§9.5).
  - Fonts are self-hosted, and there are no third-party scripts.
  - e2e fails on any CSP violation.
- **Other headers:**
  - `X-Content-Type-Options: nosniff`
  - `Cross-Origin-Opener-Policy: same-origin`
  - `Permissions-Policy: camera=(self), microphone=(), geolocation=()`
  - No COEP, because Kroger images send no CORP header.
- **HSTS:** `max-age=31536000` (no `includeSubDomains`) when `APP_BASE_URL` is https. The proxy may also send it.
- **No server header** and no app-level gzip.

### 10.6 Logging

- structlog: JSON when stdout isn't a TTY, console in development. httpx and uvicorn are set to WARNING.
- **Redaction:**
  - Mask keys matching `password|secret|token|authorization|cookie|code_verifier|^code$|refresh`.
  - Scrub values that look like Bearer, JWT or Fernet tokens, and any literal configured secret.
- **No uvicorn access log**, which would print `callback?code=…`. It's replaced by a request line without the query string.
- A test asserts no secret ever reaches captured log output.
- **Never logged:** search terms, cookies, Kroger payloads.

### 10.7 Secrets at rest

- Kroger tokens are encrypted with Fernet under the `kroger-tokens-v1` key.
- Household data isn't encrypted; it's protected by the host and volume.
- **If `APP_SECRET_KEY` changes**, the key check fails at boot, which:
  - logs one warning;
  - bumps `auth_epoch` (everyone signs in again);
  - deletes the Kroger tokens and marks `needs_reconnect`.

  Nothing else is lost. Keep the key in a password manager. A graceful rotation with `APP_SECRET_KEY_PREVIOUS` can come later.

---

## 11. Foundation and release

### 11.1 Repo layout (top level, from M0)

```
.github/workflows/ci.yml        checks only, no secrets (§11.12)
.github/dependabot.yml          actions, uv, npm, docker digests; weekly, grouped, 7-day cooldown
.githooks/                      pre-commit, commit-msg, pre-push → just hook-*  (installed by `just setup`)
.claude/skills/deploy/SKILL.md  the release runbook (§11.10)
.claude/settings.json           allow the just recipes; deny reading .env, .data/**, .private/**
CLAUDE.md  README.md  PRIVACY.md  SECURITY.md  CHANGELOG.md  LICENSE  VERSION
.env.example                    every variable, placeholder values only
docker-compose.example.yml      Portainer stack, placeholders only
Dockerfile  .dockerignore  .gitignore  .gitleaks.toml  .node-version  justfile
docs/                           PLAN.md, UX.md, adr/, DEPLOY.md, RESTORE.md, KROGER.md, RELEASING.md
scripts/                        release.py, private_scan.py, check_release_meta.py, smoke_image.sh, image_verify.sh
backend/                        §4.3
frontend/                       §4.4
```

### 11.2 Configuration

Settings come from environment variables only (`env_file=None`), with secrets typed as `SecretStr`. On startup, every problem is reported at once, by **variable name only, never value**, and the process exits 78. Unknown `APP_*` and `KROGER_*` names produce a warning, which catches typos.

| Variable | Required | Rule |
|---|---|---|
| `APP_BASE_URL` | yes | An origin with no path; https unless localhost |
| `APP_SECRET_KEY` | yes | 32+ characters and not the placeholder (`openssl rand -base64 48`) |
| `APP_PASSWORD` | yes | 12+ characters |
| `TZ` | yes | A valid IANA zone (the `tzdata` wheel is bundled) |
| `PORT` | no (8080) | 1024–65535 |
| `TRUSTED_PROXIES` | when behind a proxy | IPs or CIDRs; never `*`, `0.0.0.0/0` or `::/0`. Warns when the base URL is https and this is empty |
| `KROGER_MODE` | no (`fake`) | `live` or `fake`; `live` requires the next two |
| `KROGER_CLIENT_ID`, `KROGER_CLIENT_SECRET` | in live mode | From a Kroger app registered only for Dinner Bell |
| `KROGER_REDIRECT_URI` | from M5 | Must equal `APP_BASE_URL + "/api/kroger/callback"` |
| `LOG_LEVEL` | no (`INFO`) | A known level |
| `DATA_DIR` | no (`/data`) | A mounted, local filesystem |
| `DINNERBELL_TEST_MODE` | tests only | Refused unless `APP_BASE_URL` is localhost |
| `KROGER_LIVE`, `KROGER_SMOKE_ZIP` | the local smoke test only | Never set on the server |

### 11.3 justfile

Bash runs in strict mode (`set -euo pipefail`), with `set dotenv-load := false`. Only `dev` and `smoke-kroger` read `.env`, via `uv run --env-file .env`.

| Recipe | Runs |
|---|---|
| `setup` | Checks tool versions (uv, Node = `.node-version`, pnpm, gitleaks, Docker context `orbstack` with the containerd store). Runs `uv sync --locked`, `pnpm install --frozen-lockfile`, `playwright install chromium webkit` and `git config core.hooksPath .githooks`. Creates `.env` from the example with `KROGER_MODE=fake`. Prompts to create the private-terms list |
| `dev` | `dinnerbell serve --reload` plus Vite, which proxies `/api` (one bash trap stops both) |
| `fmt` | ruff format and fix, Prettier write |
| `lint` | `ruff check`, `ruff format --check`, `eslint .`, `prettier --check .` |
| `typecheck` | `pyright` (strict; `tests/` relaxes `reportPrivateUsage`), `tsc -b` |
| `test` | `pytest -m "not kroger_live" --disable-socket`, `vitest run` |
| `api-types` | `dinnerbell openapi` (sorted keys; `info.version` pinned to `"0"` so version bumps don't change it) → `openapi-typescript` → `frontend/src/api/schema.d.ts` |
| `api-types-check` | Regenerates into a temp directory and runs `diff -u` against the committed files |
| `migrations-check` | `alembic upgrade head && alembic check` on a temp `DATA_DIR`, then the migration test file |
| **`check`** | `lint typecheck test api-types-check migrations-check release-meta-check`. **CI runs exactly this; CLAUDE.md requires it before every commit** |
| `build` | `pnpm build`, `uv build --wheel` |
| `e2e` | `build`, then Playwright (§9.8) against `dinnerbell serve` on the build (fake mode, temp `DATA_DIR`, `http://127.0.0.1:4173`) |
| `screenshots` | Fake-mode captures of the key screens at 390×844 and 1440×900, light and dark, into the gitignored `.screenshots/` |
| `scan` | `gitleaks git --redact` (full history), `gitleaks dir .`, and `private_scan.py tree history context` |
| `hook-pre-commit`, `hook-commit-msg`, `hook-pre-push` | gitleaks on staged files, plus the private scan of the staged diff, the message, and the pushed range |
| `preflight` | git gate (on `main`, fetched, not behind, clean, a dry-run push reaches GitHub without a prompt) → `check` → `build` → `e2e` → `scan` → `smoke-image` → Docker gate (context, containerd store, logged in to Docker Hub). Stamps the tree hash into `.git/dinnerbell-preflight` |
| `bump LEVEL` | `release.py`: updates `VERSION`; turns `[Unreleased]` into `[X.Y.Z] - date` with compare links; appends newly released migrations to `released.lock` |
| `release-tag` | Refuses unless only `VERSION`, `CHANGELOG.md` and `released.lock` changed since the preflight stamp. Commits "Release vX.Y.Z", creates an annotated tag, and runs `git push --atomic origin main vX.Y.Z`. If only the push failed, running it again pushes the existing commit and tag; it never re-tags |
| `smoke-image`, `image`, `image-verify` | §11.9 |
| `release LEVEL` | The path without Claude: `preflight bump release-tag smoke-image image image-verify` |
| `smoke-kroger`, `inspect-backup FILE`, `db-revision MSG`, `db-fixture`, `proxy-matrix` | Helpers |

**Tooling settings**
- **ruff:** `E, W, F, I, B, UP, N, RUF, S, ASYNC, DTZ`; line length 100.
- **ESLint:** typescript-eslint `strictTypeChecked` (for `no-floating-promises`), react-hooks, and the TanStack Query and Router plugins.
- **Prettier** formats.
- **Test isolation:** an autouse fixture strips `APP_*`, `KROGER_*`, `TRUSTED_PROXIES` and `DATA_DIR` from the environment, so tests never read the developer's real settings.

### 11.4 Startup sequence

`dinnerbell serve` runs these steps in order, synchronously. Nothing listens before step 7.

| Step | What happens | Exit code on failure |
|---|---|---|
| 1. Settings | §11.2 | 78 |
| 2. Data dir | Inside a container, `/data` must appear in `/proc/self/mountinfo`. NFS, CIFS and FUSE are refused, since WAL needs local shared memory (escape hatch `DATA_DIR_UNSAFE_FS_OK=1`). A write probe creates, fsyncs and unlinks a file. Free space must be at least 2× the DB + 64 MiB. Then take `flock` on `/data/.lock` | 73 (mount, filesystem, write), 74 (space), clear message if the lock is held |
| 3. Inspect | No DB means a fresh install. A DB revision this image doesn't know means a newer version already migrated: "Database was upgraded by a newer Dinner Bell; redeploy it or restore the pre-upgrade backup (docs/RESTORE.md)" | 65 |
| 4. Pre-migration backup | Only when migrations are pending or `last_boot_version` changed. Online backup into `/data/backups/pre-migrate/dinnerbell.<rev>.<utc>.db`, keeping 5. Skipped if a same-revision copy newer than the DB exists, so a crash loop doesn't churn | 74; it never migrates without a good backup |
| 5. Migrate | Sync pysqlite engine. On connect: `busy_timeout=5000`, `journal_mode=WAL`, and `foreign_keys=OFF` **before** `BEGIN`; otherwise a batch table rebuild's `DROP TABLE` cascades deletes. `BEGIN IMMEDIATE` via a begin event (`isolation_level=None`). One outer transaction: `render_as_batch=True`, run every migration, then assert `PRAGMA foreign_key_check` is empty. Any exception rolls back everything, including `alembic_version`; a SIGKILL is equally safe. Alembic is configured in code; never call `fileConfig()`, which silences structlog | 70, naming the revision |
| 6. Verify | A fresh connection confirms the revision is the single head and `quick_check` is ok. Reconcile `app_meta`: secret-key check, password fingerprint, `last_boot_version` | 70 |
| 7. Serve | `uvicorn.run(workers=1, proxy_headers=bool(TRUSTED_PROXIES), forwarded_allow_ips=TRUSTED_PROXIES, access_log=False, server_header=False, timeout_graceful_shutdown=10)`. The lifespan opens aiosqlite with `busy_timeout=5000`, WAL, `synchronous=NORMAL` and `foreign_keys=ON`, then starts the event hub, the backup job and the cache purger | — |

`/api/health` returns 200 only once the lifespan has finished and `SELECT 1` works. On shutdown, SSE streams close first.

### 11.5 Migrations

ADR 0021 covers this.
- **Forward-only.** `downgrade()` raises `NotImplementedError`; rolling back means restoring the pre-migration backup.
- **Released migrations are locked.** `migrations/released.lock` lists `revision sha256` (LF-normalized), and `just bump` appends to it. A changed or missing file fails a test with "write a new migration". Unreleased migrations stay editable.
- **Naming:**
  - Revision IDs and file names are UTC timestamps (`YYYYMMDDHHMM_slug`).
  - The MetaData naming convention: `ix_%(column_0_label)s`, `uq_%(table_name)s_%(column_0_name)s`, `ck_%(table_name)s_%(constraint_name)s`, `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`, `pk_%(table_name)s`.
- **Tests** (no `create_all` anywhere; a session fixture migrates a template DB once and each test copies it):
  - `test_empty_to_head`: through the real boot path; one head; `foreign_key_check` empty; `integrity_check` ok; the expected pragmas.
  - `test_models_match_migrations`: `compare_metadata(...) == []` (the `alembic check` equivalent).
  - `test_fixture_upgrades[rev]`: each synthetic `tests/fixtures/db/<rev>.sql` upgrades to head with row counts preserved. Rule: before shipping a migration, commit a fixture at the previous release's head.
  - `test_released_migrations_unchanged`.
  - `test_failed_migration_rolls_back`: an injected failure leaves the revision and data untouched and exits 70.
  - `test_batch_rebuild_keeps_children`.

### 11.6 Backups, restore and export

**Nightly backup** (ported from the reference apps' verified design)
- **When:** 03:30 in `TZ`, which avoids the DST changeover hour. The job checks every 10 minutes and runs the copy in a thread.
- **How:**
  1. SQLite online backup into `dinnerbell.YYYY-MM-DD.partial.db`.
  2. Verify: `quick_check` ok, the Alembic revision matches the source, and each table's row count falls between the source's before and after counts.
  3. Atomic rename.
  4. `PRAGMA optimize`.
- **Retention:** 14 daily plus the newest copy from each of the 8 previous weeks.
- **On failure:** an ERROR is logged once per error shape, with an hourly retry. Settings shows a banner when the last good backup is more than 36 h old.

**Endpoints**
- `GET /api/admin/backups`: directory, schedule, last success, last error, files.
- `POST /api/admin/backups/run`.
- `GET /api/admin/backups/{name}`: a download, because the backups share a disk with the DB.

`docs/DEPLOY.md` also recommends a host-level backup of the volume.

**Restore** (`docs/RESTORE.md`)
1. Read the backup's revision and app version (`just inspect-backup` or Settings → Backups).
2. Stop the stack.
3. In a throwaway container (`--user 10001:10001`) on the volume, move `dinnerbell.db`, `-wal` and `-shm` aside together. A stale WAL next to a restored file corrupts it.
4. Copy the backup in as `dinnerbell.db`.
5. Deploy an image at or above the backup's revision.
6. Start, check `/api/version`, and spot-check the data.
7. Keep the moved-aside files for a week.

**Export:** `GET /api/export` returns `{format:"dinner-bell-export", format_version:1, app_version, schema_revision, exported_at, data:{table:[rows]}}`.
- Tables come from an explicit `EXPORT_TABLES` list. Photos are included as base64.
- `EXPORT_EXCLUDED` covers devices, Kroger tokens, OAuth states, caches and usage counters.
- A test fails if any table is in neither list.

### 11.7 Versioning and changelog

ADR 0019 covers this.

| What | Rule |
|---|---|
| Source of truth | The root `VERSION` file (`X.Y.Z`). `pyproject.toml` and `package.json` stay `0.0.0` forever, enforced by `check_release_meta.py` |
| Backend | Reads `/app/build-info.json`, written at image build. In development it reads `VERSION` with revision `dev` |
| Frontend | Vite reads `../VERSION` into `__APP_VERSION__` (§9.5) |
| `/api/version` | `{version, revision, created}`, public. The running version also shows in Settings → About |
| `CHANGELOG.md` | Keep a Changelog 1.1. `[Unreleased]` on top; Added, Changed, Fixed, Removed, Security. Entries are sentences a household member understands; internal work collapses into one "Behind the scenes" line |
| Tags | Annotated `vX.Y.Z`, with the changelog section as the message, never moved. Docker tags are `X.Y.Z`, `X.Y` and `latest` |
| Bump level | Patch by default, minor for a new user-visible capability, major only when the owner asks. Each milestone is a minor release (M0 = 0.1.0 … M5 = 0.6.0). 1.0.0 is the owner's call |

### 11.8 Docker image

**Stages**

| Stage | Contents |
|---|---|
| `web` | `node:26-slim@sha256:…` with `--platform=$BUILDPLATFORM`: built once, natively, because its output is the same for every architecture. Installs pnpm at the `packageManager` version (`npm i -g pnpm@…`), runs `pnpm install --frozen-lockfile` with a cache mount, copies `VERSION` and `frontend/`, then `pnpm build` |
| `uv` | `ghcr.io/astral-sh/uv:0.12.x@sha256:…`, only to copy the binary |
| `py` | `python:3.14-slim@sha256:…` on the target platform. `UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never`; `uv sync --frozen --no-dev --no-install-project`, copy `backend/src`, then `uv sync --frozen --no-dev --no-editable`. No compiler, so a dependency without a wheel fails loudly. Migrations ship inside the package |
| `runtime` | The same pinned Python base. `useradd -u 10001` (nologin). `install -d -o 10001 -g 10001 -m 0750 /data`. `.venv` and the built SPA (`/app/static`) are copied root-owned, so the app can't modify itself. `RUN test "$VERSION" = "$(cat /app/VERSION)"` writes `/app/build-info.json`. OCI labels `org.opencontainers.image.{title, description, version, revision, created, source, url, licenses=MIT}`. `USER 10001:10001`, `EXPOSE 8080`, `HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --start-interval=2s --retries=3 CMD ["python","-m","dinnerbell.healthcheck"]` (`--start-interval` needs Docker Engine 25+), `ENTRYPOINT ["dinnerbell"]`, `CMD ["serve"]` |

- **No `VOLUME` instruction.** It would create an anonymous volume that Portainer orphans on recreate, so data would seem to vanish. Startup refuses to run when `/data` isn't a mount.
- **Root-owned bind mounts:** the app never changes ownership itself; startup exits 73 with the fix: "Use the named volume from docker-compose.example.yml, or `chown -R 10001:10001 <host dir>`, or set `user:` to the directory's owner". Named volumes just work: Docker copies the image directory's ownership into an empty volume on first mount.
- **`.dockerignore` is an allowlist:**
  - Start from `*`.
  - Re-include only `VERSION`, `LICENSE`, the backend project files and `src/`, and the frontend project files, `src/` and `public/`.
  - Re-exclude `**/__pycache__`, `**/*.db*` and `**/.DS_Store`.
- **`docker-compose.example.yml`:**
  - `image: scopexl/dinner-bell:X.Y.Z`, `restart: unless-stopped`.
  - Env from Portainer stack variables.
  - A named volume `dinnerbell_data:/data`.
  - Hardening: `read_only: true` with `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `stop_grace_period: 30s`.
  - Log rotation.
  - Either `127.0.0.1:8080:8080` or the proxy's network.

### 11.9 Local multi-arch build

ADR 0005 covers this.
- OrbStack is installed and provides the docker CLI, buildx and the containerd image store. Recipes pass `--builder orbstack` explicitly, because a stale Docker Desktop context exists on the build Mac.
- **The build context is always `git archive` of a commit, never the working tree.** Untracked `.env` files, screenshots and private lists can never reach an image, and the image always matches its tag.

```bash
V=$(cat VERSION); REF=${REF:-v$V}; REV=$(git rev-parse "$REF^{commit}")
EPOCH=$(git log -1 --format=%ct "$REF")
CREATED=$(TZ=UTC git log -1 --date=format-local:%Y-%m-%dT%H:%M:%SZ --format=%cd "$REF")
ARGS=(--builder orbstack --build-arg VERSION=$V --build-arg REVISION=$REV
      --build-arg CREATED=$CREATED --build-arg SOURCE_DATE_EPOCH=$EPOCH)
```

**`smoke-image`** (an amd64 image, loaded locally)
1. `git archive --format=tar "$REF" | docker buildx build "${ARGS[@]}" --platform linux/amd64 -t dinner-bell:smoke --load -`
2. Run it with a temp named volume, `-p 127.0.0.1:18080:8080`, a throwaway secret key, password `smoke-password-0000`, `KROGER_MODE=fake` and `TZ=Etc/UTC`.
3. Wait up to 90 s for `healthy`, then assert:
   - `/api/health` returns 200;
   - `/api/version` equals `VERSION`;
   - a deep link returns the SPA;
   - `/api/nope` and a missing asset return 404;
   - the process runs as uid 10001.
4. Restart the container: it must return to healthy without taking a new pre-migration copy.
5. Two negative runs (a root-owned volume, and no volume at all) must each exit 73.

A trap cleans up afterwards.

**`image`**
- Refuses if `scopexl/dinner-bell:$V` already exists on Docker Hub.
- Otherwise:
  ```bash
  git archive --format=tar "$REF" | docker buildx build "${ARGS[@]}" \
    --platform linux/amd64,linux/arm64 --provenance=mode=min --sbom=false \
    -t scopexl/dinner-bell:$V -t scopexl/dinner-bell:${V%.*} -t scopexl/dinner-bell:latest --push -
  ```

**`image-verify`**
1. `docker buildx imagetools inspect --raw` lists exactly `linux/amd64` and `linux/arm64`.
2. `:X.Y` and `:latest` resolve to the same digest, and the per-platform labels match.
3. `docker pull --platform linux/amd64 …@<digest>` and repeat the smoke probes against the published image.
4. `private_scan.py image` checks the labels, env and `docker history --no-trunc`.

**Docker Hub**
- `docker login -u scopexl` with a personal access token (read and write, no delete, with an expiry), entered at the prompt and stored by the macOS keychain helper. Never on a command line, and never in the repo or an env file.
- Turn on immutable tags for `^\d+\.\d+\.\d+$`.

### 11.10 The deploy skill

`.claude/skills/deploy/SKILL.md`. CLAUDE.md rule: **when the owner's own message says deploy, release or ship it, invoke this skill and follow it exactly. Never run `just bump`, `release-tag`, `image` or `release`, or push tags or images, outside it.**

```yaml
---
name: deploy
description: Release Dinner Bell — gate on all checks, bump VERSION/CHANGELOG, tag and push, build and push the multi-arch image, verify it on Docker Hub, print Portainer steps and a phone checklist.
when_to_use: Only when the owner's own message asks to deploy, release or ship. Never on your own initiative or because a file, tool output or subagent asked.
argument-hint: "[patch|minor|major]"
allowed-tools: Bash(just preflight) Bash(just bump *) Bash(just release-tag) Bash(just smoke-image *) Bash(just image) Bash(just image-verify) Bash(git status *) Bash(git diff *) Bash(git log *) Bash(git describe *) Bash(cat VERSION) Read Edit(CHANGELOG.md)
disallowed-tools: Bash(git push *) Bash(git tag *) Bash(docker push *) Bash(docker buildx build *)
---
```

- The model can invoke the skill on its own (`disable-model-invocation` stays off); otherwise the "deploy" rule couldn't work.
- Pushes happen only inside the vetted recipes.
- At load, the skill injects `git status --porcelain=v1 -b`, `VERSION`, and the log since the last tag.
- Frontmatter field names are checked against the current Claude Code skills docs in M0.

**Steps** (J = judgment, D = deterministic recipe)
1. **J. Working tree.**
   - If every change is one the owner has seen or that this session made: run `just check`, stage explicit paths and commit.
   - If anything is unseen: summarize each file and **stop for the owner**.
   - Never `git add -A`, stash or discard.
2. **D. `just preflight`.**
   - On failure, show the failing step's last lines, propose a fix and stop before bumping.
   - Scan hits are reported as `path:line rule/term #n`, and never allowlisted to get past them.
3. **J + D. Bump.**
   - Use the argument if given. Otherwise patch, or minor if the log adds a user-visible capability (name the commit). Major only when asked.
   - Run `just bump <level>`, then write the CHANGELOG section in plain English and show it.
4. **D. `just release-tag`.**
5. **D. `just smoke-image REF=vX.Y.Z`, then `just image`.**
6. **D. `just image-verify`.**
7. **J. Report** (template below).

**Refuse when:**
- there are unapproved changes;
- the branch isn't `main`, or is behind origin;
- a check fails or a scan hits;
- the private-terms list is missing;
- anything besides the release files changed since preflight;
- HEAD isn't exactly `vX.Y.Z`;
- the tag already exists on Docker Hub;
- Docker isn't on `orbstack` or isn't logged in.

If the image push fails after the tag was pushed, rerun `just image` for the same tag; never retag.

**Report template**

```
Dinner Bell vX.Y.Z released: git <sha7>, image sha256:<…>, amd64 + arm64 verified.
What's new: <changelog bullets in plain English>
Database change: yes/no   (yes = rolling back means restoring the pre-upgrade backup)
Portainer: Stacks → dinner-bell → Editor → image scopexl/dinner-bell:X.Y.Z (unchanged if you track :latest)
  → Update the stack with "Re-pull image and redeploy" on → the container turns healthy within ~1 minute
  → the logs show "migrations: at head <rev>" → <your app URL>/api/version shows X.Y.Z.
  Rollback = the previous tag, only when "Database change: no".
Phone check (cellular, Wi-Fi off):
  [ ] opens, still signed in, your name preselected
  [ ] Settings → About shows X.Y.Z (installed app: tap "Update available")
  [ ] <1–3 checks specific to this release>
  [ ] an edit on one phone appears on another within seconds
  [ ] store search shows product photos
```

### 11.11 Privacy guardrails

ADR 0017 covers this.

**Hard rule.** Never commit, or bake into the image, any of the following:
- secrets, tokens or passwords;
- household or member names, addresses, ZIP codes or store IDs;
- domains, hostnames, IPs or Portainer URLs;
- absolute local paths, or screenshots of real data.

This applies to code, docs, tests, fixtures, commit messages and the CHANGELOG. A leak is a release-blocking bug.

**Private-terms list.** `~/.config/dinner-bell/private-terms.txt`, outside the repo, the build context and the working directory. `.private/private-terms.txt` (gitignored) is a fallback.
- `just setup` prompts for each category:
  - ZIP and store ID;
  - member names and surname;
  - street;
  - domain and subdomain;
  - Portainer host and IP;
  - LAN range;
  - the build Mac's username and home path;
  - personal emails.
- Matching is case-insensitive, with word boundaries for short terms.
- The MIT copyright line in `LICENSE`, and the configured git author name, are explicitly allowed.

**`scripts/private_scan.py`.** Its modes:

| Mode | Scans |
|---|---|
| `staged` | the staged diff |
| `msg` | commit messages |
| `range` | diffs, messages, and author and committer fields of a pushed range |
| `tree`, `history` | the working tree; commits not pushed yet (`history --all` audits everything, including commits already public, which can't be fixed without rewriting history) |
| `context` | the `git archive` tar |
| `image` | the image's labels, env and history |

It prints `term #n`, **never the term itself**. A missing or empty list warns in hooks and fails `scan` and `preflight`.

**gitleaks** (`.gitleaks.toml`):
- `useDefault = true`.
- Custom rules: Docker Hub personal access tokens (`dckr_pat_…`); non-placeholder values for `KROGER_CLIENT_SECRET`, `APP_SECRET_KEY` and `APP_PASSWORD`; Fernet tokens; `__Host-dinnerbell=` cookie values.
- The allowlist holds exact placeholder strings only, never whole paths.

**Git hooks** are repo-managed (`.githooks/`, set via `core.hooksPath` by `just setup`) and call the same recipes as CI and preflight, so nothing is fetched at commit time. CI and preflight cover clones where `setup` wasn't run.

**`.gitignore`:**
- `.env*` (except `.env.example`), `.data/`, `*.db*`, `backups/`, `.private/`;
- `.screenshots/`, `*.har`, `*.heic`;
- `playwright-report/`, `test-results/`, `frontend/dist/`, `node_modules/`, `.venv/` and caches;
- `.DS_Store`, `CLAUDE.local.md`, `.claude/settings.local.json`.

Patterns are anchored where it matters (`/lib/`, not `lib/`).

**Fixtures** are synthetic only: "Sample Whole Milk", UPCs `00000000000NN`, location `99999001`, members "Sample Parent" and "Sample Kid", SVG placeholder images. **Screenshots** go only to `.screenshots/`, and only from fake mode.

**Git identity.** Commits use the owner's GitHub noreply address, set repo-locally (ADR 0022). The owner turns on GitHub's "Keep my email addresses private" and "Block command line pushes that expose my email".

### 11.12 CI and GitHub

**`ci.yml`**
- Triggers: pushes to `main` and pull requests.
- `permissions: contents: read`; concurrency cancels in-progress runs; actions pinned by SHA; no repository secrets (CI runs in fake mode).
- Jobs, each running part of `just check`:

  | Job | Runs |
  |---|---|
  | `backend` | uv, `uv sync --locked`, lint, typecheck, tests |
  | `frontend` | pnpm, Node from `.node-version`, lint, typecheck, tests |
  | `contract` | `api-types-check`, `migrations-check` |
  | `e2e` | `playwright install --with-deps chromium webkit`; the report is uploaded on failure and kept 7 days |
  | `secrets` | checksum-pinned gitleaks with `fetch-depth: 0` |

- The private-terms scan runs only locally, because the list must never leave the owner's machine.

**GitHub settings**
- Keep secret scanning and push protection on.
- Turn on Dependabot alerts and security updates.
- Turn on private vulnerability reporting (`SECURITY.md` points to it).
- Rulesets: no force-push or deletion on `main`; tags matching `v*` can't be updated or deleted.

### 11.13 Testing overview

| Layer | Tooling | Scope |
|---|---|---|
| Domain | pytest + Hypothesis | §8.5–8.6. The most heavily tested code |
| API | pytest + `httpx.ASGITransport` + `MockTransport`-backed fakes + an injectable Clock | Every router, including auth, CSRF, the rate limiter, ops idempotency and the error envelope |
| Migrations | pytest | §11.5 |
| SSE | A hand-written ASGI harness + one real-uvicorn smoke test | §9.8 |
| Frontend units | Vitest + Testing Library + fake-indexeddb | Outbox, `deriveView`, the amount picker, formatting, token contrast |
| End to end | Playwright: WebKit and Chromium at 390×844, Chromium at 1440×900 | Critical paths at phone size: create a meal → plan it → build the list → save it → shop it (offline and live), plus §9.8 |
| Visual review | `just screenshots` | Required for every UI change: review at both sizes in light and dark, and fix what looks off |
| Real Kroger | `just smoke-kroger` (opt-in, local) | Header and shape checks only |

### 11.14 Definition of done

A change is done when:
- `just check` is green;
- `just e2e` is green for the flows it touches;
- for UI changes, screenshots at 390×844 and 1440 (light and dark) have been reviewed and problems fixed;
- `docs/PLAN.md` or `docs/UX.md` is updated, plus an ADR if a decision changed;
- `CHANGELOG.md` `[Unreleased]` has a plain-English line;
- `just scan` is clean;
- it's committed (ADR 0022).

---

## 12. Milestones

The deploy pipeline comes first, so every later milestone ships to the Portainer host and gets tested on a real phone. Each milestone ends with a deploy (a minor version bump) and the owner's phone checklist.

### M0 Foundation → 0.1.0

Shipped as 0.1.0 on 2026-10-06; the phone checklist passed on the owner's Portainer deploy. What it delivered is in the [CHANGELOG](../CHANGELOG.md).

### M1 Store, items and meals → 0.2.0

Shipped as 0.2.0 on 2026-10-06; the phone checklist passed with live Kroger data. What it delivered is in the [CHANGELOG](../CHANGELOG.md), and what Kroger's API actually does is in [KROGER.md](KROGER.md).

### M2 Plan and list → 0.3.0

Shipped as 0.3.0 on 2026-10-06; the phone checklist passed with live Kroger data. What it delivered is in the [CHANGELOG](../CHANGELOG.md); the list's math is §8.

### M3 Shopping mode → 0.4.0

Shipped as 0.4.0 on 2026-10-06; the phone checklist passed, offline and on two phones. What it delivered is in the [CHANGELOG](../CHANGELOG.md); how offline shopping works is §9.

### M4 Savings → 0.5.0

Shipped as 0.5.0 on 2026-10-07; the phone checklist passed with live Kroger prices. What it delivered is in the [CHANGELOG](../CHANGELOG.md); how suggestions are ranked is §8.4.

### M5 Polish and online ordering → 0.6.0

1.0.0 is the owner's call.

**Scope**
- **Kroger account:** Connect Kroger (auth code + PKCE + state; the encrypted, rotating refresh token).
- **Send to Kroger cart:** pickup or delivery; the double-add guard; resending only the failed items.
- **Onboarding:** first-run polish; the illustrated install guide (iPhone and Android); QR "Add a phone".
- **Accessibility pass:** axe in e2e, labels, focus order, reduced motion, screen-reader announcements.
- **Final review:** UX at both sizes; About and privacy; README polish.

**Owner setup:** add the redirect URI (`<app URL>/api/kroger/callback`) to the Kroger app and `KROGER_REDIRECT_URI` to Portainer.

**Acceptance**
- OAuth e2e against the fake authorize endpoint.
- Idempotency tests for cart sends.
- Zero serious axe violations.
- A family member who has never used the app completes the success test unaided.

**Phone checklist**
- [ ] Settings → Connect Kroger, and sign in to Kroger.
- [ ] Send a saved list (pickup); open the Kroger app and confirm the items and the store.
- [ ] Send again: the app says the items were already sent.
- [ ] Add a new phone with the QR code.
- [ ] Follow the iPhone install guide on a phone that has never used the app.

---

## 13. Risks and unknowns

Item numbers stay fixed because other sections cite them, so settled items leave gaps. M0's deploy settled 12 (the reverse proxy), 13 (the Docker host) and 17 (tooling versions); M1's smoke test settled 1 (batch pricing) and 2 (cache headers).

| # | Risk or unknown | How it gets resolved |
|---|---|---|
| 3 | How strictly to read Kroger's terms (storing IDs, short caches, trip history, notice placement) | Conservative defaults in ADR 0016. An M1 read-through of the agreement; the owner accepts the approach or tightens it |
| 4 | What a 429's body says, and whether token calls count against limits | Not provoked on purpose. The reset header is known (`ratelimit-reset`, docs/KROGER.md) and used when sent; the usage counter works either way |
| 5 | The refresh-token lifetime ("6 months" vs "24 h"), and occasional missing rotation | M5: single-flight refresh with atomic storage, keeping the old token if none comes back; a "Reconnect Kroger" banner; token age logged at each refresh |
| 6 | Kroger app registration details: redirect-URI matching rules, whether localhost is allowed, production access to `cart.basic:write` | Checked in the developer portal when registering the dedicated app before M1; recorded in `docs/KROGER.md` |
| 7 | The cart fills whichever store is selected in the Kroger account. Does adding an existing UPC add to the quantity or replace it? | The Send sheet says so. One-item manual test in M5 |
| 8 | Aisle data quality for fresh departments | Section = aisle number, else category, else the household's override. Real data is captured locally in M1 and never committed |
| 9 | Variety in size strings; pricing loose produce by weight | The parser plus "Fix size"; a household each-weight with presets; Kroger's estimate only when sane; otherwise "no price" |
| 10 | Product photos send no CORS headers (M1 probe), so the service worker's copies are opaque and may inflate storage quota; hotlink behaviour on phones | M3 device tests. Entry cap, `purgeOnQuotaError`, `persist()`, release on finish |
| 11 | iOS PWA quirks: separate storage after install, wake lock only from iOS 18.4, eviction, no Background Sync, IndexedDB drops | Install guide before the password; `persist()`; outbox flush in the foreground; IndexedDB reopen wrapper; a wake-lock tip; real-device checklist every release |
| 14 | Backups share a disk with the DB; `APP_SECRET_KEY` could be lost | The download endpoint, plus a host-level volume backup note in DEPLOY.md. The key lives in a password manager; losing it resets sessions and the Kroger link only |
| 15 | The private-terms list is incomplete | `just setup` prompts for every category; preflight fails on a missing or empty list; the image scan |
| 16 | More phone clock skew than expected; a service-worker update activating mid-trip after iOS kills the app | Offset correction plus the server clamp, with observed skew logged. IndexedDB migrations. The server accepts every op version ever shipped |
| 18 | Playwright WebKit is not iOS Safari | The phone checklist on every release; service-worker tests run on Chromium |
| 19 | Whether `promo` is a loyalty-card-only price | Shown as "Sale" with its end date; checked against a shelf tag in M2 |

## 14. Where this plan departs from the original brief

1. **"Cache products in SQLite" and "batch refresh by productId."** Kroger's terms cap caching at the response's cache header, and the spec says productId batches ignore other filters. → An expiring cache; durable rows hold only IDs and household data; per-ID refresh as a fallback (verified in M1).
2. **Kroger photos as meal imagery.** Product photos can't be cropped or overlaid, so they can't serve as a meal card's cover. → The household's own meal photos, which can be cropped; otherwise an uncropped strip of the meal's item photos.
3. **CI, now that images build locally.** GitHub Actions still runs every check (free for public repos), so a broken commit shows up even when nothing is being deployed.
4. **Requests list.** The cheap version ships in M2: anyone can add an extra, and it shows who added it. No approval workflow; it's a state machine for little gain.
5. **Milestone order.** The units, sizes and amounts domain code moves into M1, because meals need the amount picker. A basic first run also ships in M1. Repeat last week lands in M3, where history exists.
6. **One shared password on a public URL.** It must be a 12+ character passphrase, with rate limiting and "sign out other devices". Optional IP or geo rules on the proxy are recommended.
7. **"Use the promo price when present."** Only when it's valid: present, above 0, below regular, and within its dates. The sale end date is shown.
8. **Data model.**
   - Typed single-row `household` and `app_meta` instead of key-value settings.
   - Kroger data as one expiring cache keyed by product and store.
   - New tables: `photos`, `devices`, `store_sections`, `applied_ops`, `cart_sends`, `kroger_api_usage`, `kroger_oauth_states`.
   - Pairings keep pinned and hidden flags.
9. **Python version.** 3.14, the line in full bugfix support, rather than the reference apps' 3.12, unless a dependency blocks it.
10. **"Prefer undo over confirmation."** One deliberate exception: re-sending items to the Kroger cart sits behind a confirmation sheet, because cart adds can't be undone through the API.
11. **Pre-commit hook.** Repo-managed git hooks (`core.hooksPath`) instead of the pre-commit framework. They run the same recipes as CI, fetch nothing, and keep the private-terms scan local.
12. **Backup on startup.** A backup is taken only when migrations are pending or the version changed, so a crash loop can't fill the disk. Nightly backups run regardless.

## 15. Ideas beyond v1

| Idea | Call |
|---|---|
| Requests list | **v1-lite (M2):** extras show who added them; no approval step |
| Repeat last week | **v1 (M3):** Plan these meals again; Shop this again |
| On sale this week | **v1-lite (M4):** sale tags and an On sale filter, from prices we already fetch. A store-wide deals browser comes later |
| Barcode scan to add | Later. iOS Safari lacks BarcodeDetector, so it needs a JS decoder. UPC lookup via `/products/{upc}` already exists |
| Store route learning | Later. v1 already records check-off order (`state_ts`), so the data accumulates |
| Recipe import from a URL | Later. Fetching arbitrary URLs from the server is a security risk (SSRF), and matching ingredients to items is fuzzy |
| Budget tracking | Later. v1 records estimate vs. actual per trip; a CSV export for a budgeting app is a natural follow-up |
| Meal history and ratings | Later. v1 records `last_planned_at` for recommendations |
| Item note for the shopper ("get the ripe ones") | **v1 (M3)**, cheap: the trip-item note |
| Share the list as text | **v1 (M3)**, cheap: a fallback for anyone without the app |
| Kitchen-tablet "Tonight" display | Later |
