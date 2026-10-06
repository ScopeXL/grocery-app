# Kroger setup and verified API facts

Dinner Bell uses the public Kroger APIs for product photos, sizes, prices and aisles (M1), and
to add items to a Kroger cart (M5). The design is in [PLAN.md §7](PLAN.md#7-kroger-integration);
the caching rules are in [ADR 0016](adr/0016-kroger-data-and-terms.md).

**Status:** not connected yet. `KROGER_MODE=fake` serves synthetic sample products until M1.

## Register a Kroger app (before M1)

Use an app registered only for Dinner Bell, so other tools can't use up its daily limits.

1. Sign in at [developer.kroger.com](https://developer.kroger.com) and register a new
   **production** app. Certification apps can't use the cart.
2. Name it without the word "Kroger" (Kroger's branding rules), for example "Dinner Bell".
3. Include the **Products** and **Locations** APIs now, and **Cart** for M5.
4. Privacy policy URL: `https://github.com/ScopeXL/grocery-app/blob/main/PRIVACY.md`.
5. M5 only: add the redirect URI `<APP_BASE_URL>/api/kroger/callback`, exactly as written.
6. Put the client ID and secret in the Portainer stack variables and your local `.env`
   (`KROGER_CLIENT_ID`, `KROGER_CLIENT_SECRET`), and set `KROGER_MODE=live`. They must never be
   committed; the scans block it.

## Verified behaviour

Filled in by `just smoke-kroger` during M1. Until then, nothing from Kroger is persisted. Record
only behaviour and header values here, never product data, store IDs or credentials.

| Question | Answer | Checked |
|---|---|---|
| `Cache-Control` / `Expires` on `/products` | unverified | — |
| `Cache-Control` / `Expires` on `/locations` | unverified | — |
| Does `filter.productId` (batch) honour `filter.locationId` (prices, aisles)? | unverified | — |
| What does a 429 return (body, reset headers)? Do token calls count against limits? | unverified | — |
| Image host(s) and CORS headers on product images | unverified | — |
| Redirect-URI matching rules; production access to `cart.basic:write` | unverified | — |
