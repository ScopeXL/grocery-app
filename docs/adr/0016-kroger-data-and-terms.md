# ADR 0016: Kroger data is an expiring cache; only household data is durable

- **Status:** Accepted (pending an M1 read-through of the agreement and the real cache headers)
- **Date:** 2026-10-06

## Context

The original brief proposed caching products in SQLite and refreshing them in batches by product ID. Kroger's developer Terms and Acceptable Use Policy say:

- **Caching:** don't build databases from the content or keep cached copies longer than the cache header permits, and delete cached content when access ends.
- **Display:** show product data exactly as returned; show images in their original form, with no cropping, filters or overlays.
- **Customer data:** don't track, share or store data derived from customer searches. Delete customer cart data when shopping is finished.
- **Credentials:** never embed them in open-source projects.
- **Privacy:** provide a privacy policy.

The real Cache-Control values on API responses couldn't be verified during planning. The spec also says that when `filter.productId` is used, all other filters are ignored, so batch refreshes may come back without store prices.

## Decision

**Kept permanently.** Only the household's own data:
- item names;
- product links (productId and UPC);
- corrected sizes and each-weights;
- dish amounts, plans;
- trip records: names, quantities, estimates and totals.

**Kept as an expiring cache.** Kroger content (descriptions, prices, aisles, image URLs) lives in `kroger_product_cache`:
- Its `expires_at` comes from `max-age` minus `Age`, or from `Expires`.
- With `no-store`, `no-cache` or no header, **nothing is persisted**.
- This holds until the M1 smoke test records what Kroger actually sends, in `docs/KROGER.md`.
- Expired rows are purged hourly.

**Search.** Results are held in memory for at most 60 s. Search terms are never stored or logged.

**Trips.**
- An active trip holds the Kroger fields it needs for shopping, as temporary storage for that trip.
- After a trip finishes and its `product_cache_expires_at` passes, the Kroger descriptive fields (description, image, aisle) are cleared. History re-fetches them when viewed online.

**Product photos.**
- They are hot-linked from Kroger's image host and never stored on the server.
- On phones, the service worker keeps them for at most 3 days, and only for trips. They are deleted when the trip finishes.
- They are always shown uncropped on a white tile, with badges beside them, never on them.

**Price refresh.** Stale prices are refreshed when the plan or list is opened. Refresh uses productId batches if M1 shows they return prices; otherwise per-ID calls at low concurrency.

**Other terms.**
- Credentials come from env vars only.
- `PRIVACY.md` serves as the privacy policy, linked from the Kroger app registration and the About page.

## Consequences

- The app may make more API calls than a permanent cache would, which is well within 10,000 Products calls a day for one household.
- If Kroger's headers turn out stricter or looser, only the TTL changes; the design stays the same.
- The owner should review this approach after the M1 read-through and either accept it or tighten it, for example by also clearing estimated prices from old trips.
