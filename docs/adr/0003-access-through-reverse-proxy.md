# ADR 0003: Access over HTTPS through the existing reverse proxy, with in-app login

- **Status:** Accepted (the owner's answer to the open question)
- **Date:** 2026-10-06

## Context

Phones in the store are on cellular, not home Wi-Fi. PWA install, the service worker and the screen wake lock all require HTTPS. Three options were considered:
- HTTPS through the owner's existing reverse proxy;
- a VPN on every phone;
- home Wi-Fi only.

A VPN fails the least-technical-person test, because every family member would have to keep a VPN app connected. Wi-Fi only would rule out live sync and price refreshes in the store.

## Decision

- **Access:** the app gets an HTTPS subdomain on the owner's existing reverse proxy.
- **Login:** the app enforces its own (ADR 0004) and never relies on the proxy for authentication. The repo is public, and others may deploy it without such a proxy.
- **Forwarded headers:** trusted only from `TRUSTED_PROXIES`. A signed-in diagnostics page shows the resolved client IP, so it can be configured correctly.
- **HTTP/2 at the proxy:** recommended.
- **SSE settings:** `docs/DEPLOY.md` gives per-proxy settings for nginx/Nginx Proxy Manager, Traefik, Caddy and Cloudflare.

## Consequences

- The app is reachable from the public internet, so login hardening matters: a 12+ character passphrase, rate limiting, CSRF defence, security headers, and "sign out other devices".
- Which proxy the owner uses is still unknown. SSE is built to survive any of them: a data-event heartbeat every 15 s, `X-Accel-Buffering: no`, no app-level gzip, and a quiet polling fallback if buffering is detected. It gets checked during the M0 deploy.
