# ADR 0024: Cart sends go one item at a time; pound amounts stay in the Kroger app

- **Status:** Accepted (refines ADR 0009)
- **Date:** 2026-10-07

## Context

ADR 0009 put Send to Kroger cart in M5: add-only, never retried blindly, and a confirmation before adding anything twice. Building it raised three questions that ADR didn't settle.

1. **Chunks or single items?** `PUT /v1/cart/add` takes a list. In one call, though, one bad UPC can fail the whole list, and a timeout leaves every item in it unknown. Kroger doesn't document what happens when adds to the same cart arrive at once.
2. **Items bought by the pound.** The list buys loose produce by weight ("1 1/4 lb"). The cart's `quantity` is an integer, and Kroger's docs don't say whether it counts pounds or pieces for an item sold by weight.
3. **The sign-in page's `banner`.** The authorize URL can carry a `banner` to brand Kroger's page. The values it accepts aren't documented.

## Decision

**One item per call, in list order, one at a time.**
- Each item's `cart_sends` row is written `unknown` before its call goes out, then settled: 204 → `added`, 4xx → `failed`, a timeout, dropped connection or 5xx → `unknown`.
- A refused item fails alone. Sending stops at the first sign the rest would fail too (401, 403, 429, unreachable, no answer), and the rest stay unsent.
- Nothing is retried automatically. Items `added` or `unknown` go again only on a deliberate tap; re-sending `added` items also needs the confirmation sheet from ADR 0009.
- One send per saved list at a time, claimed in memory before anything awaits (one process: ADR 0002).

**What can't go is said, not guessed.**
- Pound amounts and plain-text extras are listed under "Add these in the Kroger app".
- Packages and pieces go as whole numbers. "Pieces" covers produce sold by weight but planned by count, such as 3 avocados.

**No `banner`.** Kroger's default sign-in page is shown.

## Consequences

- **Time:** a 40-item list is 40 calls, a few seconds in all. The sheet shows how many are left, on every phone. It is well inside the cart's 5,000 calls a day.
- **Precision:** every item's outcome is exact, and an unclear answer reads as "check your Kroger cart", never as "not sent".
- **Pound items:** the household adds them by hand in the Kroger app. If the phone check shows how Kroger counts weight, a later ADR can send them.
- **Pieces:** whether Kroger counts a weight-sold item's quantity as pieces is checked on the phone at M5 (docs/KROGER.md).
