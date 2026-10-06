# Security

## Reporting a problem

Please report security issues privately through GitHub: open the repository's **Security** tab
and choose **Report a vulnerability**. Don't open a public issue for anything that could put a
household's data at risk.

## Supported versions

Only the latest release is supported. Each installation is run by the household that deploys it,
so fixes reach a household when it pulls the new image.

## How Dinner Bell protects a household

- One household password from the server's environment; sign-in attempts are rate-limited.
- Signed, HttpOnly, SameSite session cookies per device, which can be signed out from Settings.
- A strict Content Security Policy, a CSRF header check and an Origin check on every change.
- Secrets live only in environment variables. Kroger account tokens are encrypted at rest.
- The container runs as a non-root user with a read-only filesystem apart from `/data`.
