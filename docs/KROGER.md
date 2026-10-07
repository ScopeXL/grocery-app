# Kroger setup and verified API facts

Dinner Bell uses the public Kroger APIs for product photos, sizes, prices and aisles (M1), and
to add items to a Kroger cart (M5). The design is in [PLAN.md §7](PLAN.md#7-kroger-integration);
the caching rules are in [ADR 0016](adr/0016-kroger-data-and-terms.md).

**Status:** a Dinner Bell app is registered, and the smoke test passed against it (2026-10-06).
Production switches from `KROGER_MODE=fake` to `live` at the M1 deploy.

## Register a Kroger app (before M1)

Use an app registered only for Dinner Bell, so other tools can't use up its daily limits.

1. Sign in at [developer.kroger.com](https://developer.kroger.com) and register a new
   **production** app. Certification apps can't use the cart.
2. Name it without the word "Kroger" (Kroger's branding rules), for example "Dinner Bell".
3. Include the **Products** and **Locations** APIs now, and **Cart** for M5.
4. Privacy policy URL: `https://github.com/ScopeXL/grocery-app/blob/main/PRIVACY.md`.
5. From M5 (Connect Kroger): add the redirect URI `<APP_BASE_URL>/api/kroger/callback`, exactly
   as written, for example `https://dinner.example.com/api/kroger/callback`. See
   [Connect Kroger](#connect-kroger-m5) below.
6. Put the client ID and secret in the Portainer stack variables and your local `.env`
   (`KROGER_CLIENT_ID`, `KROGER_CLIENT_SECRET`). They must never be committed; the scans block
   it.
7. Keep `KROGER_MODE=fake` in the local `.env`: development and tests use sample data, and
   `just smoke-kroger` is the only local command that calls Kroger. Set `KROGER_MODE=live` in
   Portainer when deploying M1; that release's deploy report says so.

## Connect Kroger (M5)

Sending a saved list to a Kroger cart needs the household's own Kroger account, connected once in
Settings. That uses Kroger's customer sign-in, which returns the phone to Dinner Bell at one
fixed address, so two settings must agree:

1. **On the Kroger app** (developer.kroger.com → your app → Redirect URIs), add
   `<APP_BASE_URL>/api/kroger/callback`. For example, if phones open
   `https://dinner.example.com`, add `https://dinner.example.com/api/kroger/callback`.
2. **In Portainer**, set the stack variable `KROGER_REDIRECT_URI` to that same address. The stack's
   compose file must also pass it to the container: the line
   `KROGER_REDIRECT_URI: ${KROGER_REDIRECT_URI:-}` under `environment:` (it is in
   [`docker-compose.example.yml`](../docker-compose.example.yml) from 0.6.0).

Dinner Bell refuses to start if `KROGER_REDIRECT_URI` is set to anything other than
`APP_BASE_URL + /api/kroger/callback`. Without it, Settings says Connect Kroger isn't set up.
Sample mode (`KROGER_MODE=fake`) needs neither: it uses a demo sign-in page.

## Verified behaviour

Filled in by `just smoke-kroger`. Record only behaviour and header values here, never product
data, store IDs or credentials.

| Question | Answer | Checked |
|---|---|---|
| `Cache-Control` / `Expires` on `/products` | **None.** Search, by ID and batch send only `Vary: Accept-Encoding`, so nothing is stored, not even in memory (ADR 0016). Products are fetched live, in batches | 2026-10-06 |
| `Cache-Control` / `Expires` on `/locations` and `/chains` | **None** (`Vary: Accept-Encoding` only). The chosen store is the household's own record in `stores` | 2026-10-06 |
| Does `filter.productId` (batch) honour `filter.locationId` (prices, aisles)? | **Yes:** 3 of 3 came back with store prices and aisles, so prices refresh in batches of 50 | 2026-10-06 |
| What does a 429 return (body, reset headers)? Do token calls count against limits? | Not observed (the check never provokes one). Locations and chains send `ratelimit-limit: 5000`, `ratelimit-remaining`, `ratelimit-reset` (seconds to the window's end) and `x-ratelimit-*-day`; a 429 that carries `ratelimit-reset` blocks until then. Products send no rate headers. The token response has none | 2026-10-06 |
| Image host(s) and CORS headers on product images | `https://www.kroger.com/product/images/{thumbnail,small,medium,large,xlarge}/front/{productId}`, JPEG, `Cache-Control: max-age=2592000`; no `Access-Control-Allow-Origin`, no CORP, no `Vary` (the service worker's copies will be opaque: M3) | 2026-10-06 |
| Redirect-URI matching rules; production access to `cart.basic:write` | unverified: the M5 phone check (Connect Kroger) settles it | — |
| Does adding a UPC that's already in the cart add to its quantity or replace it? | unverified: the M5 phone check (Send, then Send again anyway on one item) settles it | — |
| For an item sold by weight, does the cart's `quantity` count pieces? | unverified: Dinner Bell sends pieces for those and leaves pound amounts to the Kroger app (ADR 0024); the M5 phone check looks at one | — |
| How long do refresh tokens really last? | unknown: every refresh logs `kroger.refresh` with `token_age_h` | — |

**Shapes seen** (2026-10-06):
- The app token lasts 1800 s.
- Locations have no distance field, so stores are shown in Kroger's order (nearest first).
- `hours.open24` is lowercase.
- Promo dates are `{"value", "timezone"}` objects whose values are UTC instants (`…Z`, sometimes
  with milliseconds); all 10 seen were read.
- Fulfillment keys are camelCase (`inStore`, `shipToHome`).
- Products also carry nutrition, allergens and ratings, which Dinner Bell ignores.
