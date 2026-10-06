# ADR 0023: UI primitives without runtime style injection; TypeScript 6

- **Status:** Accepted (M0)
- **Date:** 2026-10-06

## Context

Two plan assumptions didn't survive contact with the actual libraries during M0:

1. **Style injection.** The plan named Radix primitives, vaul (bottom sheets) and sonner (toasts).
   All three inject `<style>` elements at runtime. The strict Content Security Policy
   (`style-src 'self'`, docs/PLAN.md §10.5) blocks those, and the end-to-end tests fail on any
   CSP violation.
2. **TypeScript version.** TypeScript 7.0, the new native compiler, is current, but
   typescript-eslint 8.71 supports only TypeScript `>=4.8.4 <6.1.0`. openapi-typescript also
   calls TypeScript's JavaScript compiler API, which 7.0 doesn't provide: Dependabot's first
   TypeScript 7 pull request failed both lint and the API-types check.

## Decision

**UI primitives**
- Primitives live in `frontend/src/ui/` and are built on platform features:
  - the native `<dialog>` element for sheets (focus handling, Escape and inert background come
    from the browser);
  - a small toast store and region with `aria-live` for Undo toasts;
  - lucide icons as inline SVG.
- **No dependency may inject styles at runtime.** Styling comes only from the build's CSS (the
  Tailwind tokens).

**TypeScript**
- Pin TypeScript `~6.0.3`.
- Move to 7.x when typescript-eslint and openapi-typescript support it, recorded in a new ADR.
- Dependabot skips TypeScript minor and major updates (`.github/dependabot.yml`). Lift that rule
  in the same change that moves TypeScript.

## Consequences

- The CSP stays strict, and the e2e "no CSP violations" guard keeps it honest.
- A little more UI code to own, but it is small and uses only browser features.
- The Playwright screenshot run disables the CSP check: Playwright's WebKit screenshot code
  injects its own inline style. Every other spec keeps the check on.
