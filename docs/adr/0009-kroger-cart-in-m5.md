# ADR 0009: Send to Kroger cart is in v1 (M5), on the production API

- **Status:** Accepted (the owner's answers to the open questions)
- **Date:** 2026-10-06

## Context

The household shops two ways: in a store, or with Kroger pickup or delivery. Facts verified against Kroger's API docs and specs:

**Cart**
- Cart needs the authorization-code grant with scope `cart.basic:write`. PKCE (S256) is supported.
- Refresh tokens rotate on every use. Their lifetime is documented inconsistently: "6 months" in the FAQ, "typically 24 h" in the spec.
- `PUT /v1/cart/add` returns 204. It is **add-only**: the app can't read, verify or clear the cart.
- It takes no location parameter, so items go to the store selected in the shopper's Kroger account.
- A blind retry can add items twice.

**Environments**
- Kroger's certification environment can't test the cart, because its customer login is Kroger-internal.
- The owner confirmed the credentials are for **production**. Their existing tooling already calls the production host.

## Decision

**Scope and environment**
- Ship Send to Kroger cart in M5, against the production API (`api.kroger.com`) only.
- Register a Kroger app used only by Dinner Bell, so its daily limits aren't shared with other tools.

**Connecting the account**
- A one-time **Connect Kroger** in Settings, using the authorization code with PKCE and a single-use `state`.
- The redirect URI must equal `APP_BASE_URL + /api/kroger/callback`, registered on the Kroger app.
- Tokens are Fernet-encrypted at rest, with a key derived from `APP_SECRET_KEY`.
- Refresh is single-flight and stores the rotated token atomically. If no new token comes back, the old one is kept.
- On `invalid_grant`, Settings shows **Reconnect Kroger**.

**Sending**
- Every send is recorded in `cart_sends`, and items marked `added` are never re-sent automatically.
- A timeout leaves the item `unknown` ("check your Kroger cart"), and the request is never retried blindly.
- Re-sending items already added needs a confirmation sheet. That's the one place where a confirmation beats undo, because cart adds can't be undone.
- The send sheet states plainly how many items were added, that they go to the store chosen in the Kroger account, and that review and checkout happen in the Kroger app.

**Not used:** Identity. It returns only an ID, and Kroger's acceptable-use rules forbid mapping data to it.

## Consequences

- The real refresh-token lifetime is learned by logging token ages in M5. The UI handles reconnects gracefully either way.
- Whether adding an existing UPC adds to its quantity or replaces it is unknown; a one-item manual test in M5 settles it.
