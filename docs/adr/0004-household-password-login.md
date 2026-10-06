# ADR 0004: One household password, per-device sessions, "Who's using this?"

- **Status:** Accepted (the owner's answer to the open question)
- **Date:** 2026-10-06

## Context

The household shares one plan and one list, and most members aren't technical. The alternative considered was a profile plus a PIN for each person: stronger attribution, but more typing and PIN resets to manage. There are no email accounts and no password resets in v1.

## Decision

- **The password.** One household password comes from `APP_PASSWORD` (12+ characters, a passphrase). Because it comes from the environment, there's no race on a public URL to be the first visitor to set it.
  - Login compares SHA-256 digests with `hmac.compare_digest`.
  - A stored HMAC fingerprint detects a password change, which bumps `auth_epoch` and signs out every device.
- **Sessions.** Each device gets a signed cookie `__Host-dinnerbell` (`v1.<device>.<epoch>.<mac>`).
  - Attributes: `HttpOnly; Secure; SameSite=Lax`, `Max-Age` one year. It's re-issued after 30 days, so phones in use never sign out.
  - Session keys are derived with HKDF from `APP_SECRET_KEY`.
- **"Who's using this?"** After sign-in, a big-button member picker. The choice is stored on the server's device row and drives attribution ("Checked off by Mia"); attribution never comes from request payloads. Skip is allowed, but shopping mode asks once, since check-offs need a name.
- **Devices.** Settings lists devices with **Sign out other devices** and revoke for each one.
- **CSRF.** Mutations require `X-Dinner-Bell: 1`, and `Origin` must match. `Referrer-Policy: same-origin`.
- **Rate limiting.** 5 failures per IP per 15 minutes; 50 per hour globally pauses logins for 15 minutes. Kept in memory (safe under ADR 0002).
- **Joining by QR code (M5).** A signed-in phone shows a QR code holding a single-use, 5-minute token, so a new phone can join without typing the password.

## Consequences

- Attribution is per device and member, not per authenticated person. That's fine for a household; it isn't access control between members.
- Changing the password means editing the Portainer stack variable and restarting, which signs everyone out. That is also the fix for a lost phone, alongside per-device revoke.
- An iPhone's installed web app keeps its own cookies, separate from Safari. So in a normal Safari tab on iPhone, the install guide comes before the sign-in step.
