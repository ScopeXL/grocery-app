# Architecture decision records

Each record covers one decision: the context, what was decided, and the consequences. All of them are short.

**Rules for adding and changing records**
- New decisions get the next number. To change a decision, add a new ADR that supersedes the old one, and change the old one's status to "Superseded by 00NN".
- Every open question from the original brief is answered here. If the owner skipped a question, the default was used, and the ADR says so.

| ADR | Decision | Answers |
|---|---|---|
| [0001](0001-stack-and-reference-apps.md) | Stack: mirror the owner's reference apps, with listed fixes | — |
| [0002](0002-one-container-one-worker.md) | One container, one uvicorn worker, SQLite in WAL mode | — |
| [0003](0003-access-through-reverse-proxy.md) | Phones reach the app over HTTPS through the existing reverse proxy; the app does its own login | How will phones reach the app? |
| [0004](0004-household-password-login.md) | One household password, per-device sessions, "Who's using this?" | Shared password or profile + PIN? |
| [0005](0005-local-multi-arch-images.md) | Images built locally with buildx under OrbStack, amd64 + arm64, as `scopexl/dinner-bell` | CPU architecture; Actions or local buildx; image name |
| [0006](0006-plan-shape-sides-occasions.md) | The plan is a list with an optional day; usual sides are learned; occasions are tags | By day or a list? Default sides? Occasions? |
| [0007](0007-amounts-and-quantity-math.md) | Amounts in package terms plus exact units; `Fraction` quantities; cents | Package terms or cups and tablespoons? |
| [0008](0008-first-run-starts-empty.md) | Start empty, with a guided first dinner | Sample meals or empty? |
| [0009](0009-kroger-cart-in-m5.md) | Send to Kroger cart in v1 (M5), on the production API | Cart in v1? Production or certification? |
| [0010](0010-one-store.md) | One store, with data scoped per store | One store or several? |
| [0011](0011-name-dinner-bell.md) | The app is called Dinner Bell | What should the app be called? |
| [0012](0012-visual-direction-fridge-door.md) | Visual direction: "Fridge door" | — |
| [0013](0013-license-mit.md) | MIT license | Which license? |
| [0014](0014-live-updates-sse.md) | Server-sent events for live updates | — |
| [0015](0015-offline-shopping-sync.md) | Offline shopping: snapshot, op outbox, last-writer-wins | — |
| [0016](0016-kroger-data-and-terms.md) | Kroger data is an expiring cache; only household data is durable | — |
| [0017](0017-privacy-guardrails.md) | gitleaks plus a local private-terms scan; synthetic fixtures | — |
| [0018](0018-generated-api-contract.md) | Frontend types generated from OpenAPI | — |
| [0019](0019-versioning.md) | `VERSION` file, SemVer, Keep a Changelog, tags | — |
| [0020](0020-photos-in-sqlite.md) | Meal photos stored in SQLite as WebP | — |
| [0021](0021-forward-only-migrations.md) | Forward-only migrations at startup, after a backup | — |
| [0022](0022-git-identity-and-commits.md) | Noreply commit identity; commit when green; push only on deploy | — |
