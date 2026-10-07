# Deploying Dinner Bell

How to run Dinner Bell on a Docker host (Portainer) behind an HTTPS reverse proxy. Everything
household-specific goes into Portainer's stack variables, never into this repository.

## What you need

- A Docker host, managed with Portainer (or plain `docker compose`).
- An HTTPS reverse proxy with a subdomain for the app. Phones in the store use cellular data,
  and installing to the home screen, working offline and keeping the screen awake all need
  HTTPS.
- About 200 MB of disk, plus room for backups.

## 1. Create the stack

1. In Portainer: **Stacks → Add stack**. Name it `dinner-bell`.
2. Choose **Web editor** and paste [`docker-compose.example.yml`](../docker-compose.example.yml).
3. Under **Environment variables**, add:

   | Variable | Value |
   |---|---|
   | `APP_BASE_URL` | The address phones will use, e.g. `https://dinner.example.com` (no trailing slash) |
   | `APP_SECRET_KEY` | Run `openssl rand -base64 48` and paste the result. Keep a copy in a password manager: changing it signs everyone out |
   | `APP_PASSWORD` | The household passphrase, 12 characters or more |
   | `TZ` | Your time zone, e.g. `America/New_York` |
   | `TRUSTED_PROXIES` | Your reverse proxy's IP or Docker network (see step 3). Leave empty for now |
   | `KROGER_MODE` | `fake` until Kroger is set up (docs/KROGER.md) |
   | `KROGER_REDIRECT_URI` | For Connect Kroger (send lists to the Kroger cart): `APP_BASE_URL` followed by `/api/kroger/callback`, e.g. `https://dinner.example.com/api/kroger/callback`. Register the same address on the Kroger app (docs/KROGER.md) |

4. **Deploy the stack.** The container turns **healthy** within about a minute.

All data lives in the `dinnerbell_data` named volume. A named volume gets the right ownership
automatically. If you'd rather use a bind mount, see *Troubleshooting* below.

## 2. Point the reverse proxy at it

- Forward your subdomain to the container on port `8080` (or join the container to the proxy's
  Docker network and remove the `ports:` lines).
- Turn on **HTTP/2** for the host. Browsers allow only six HTTP/1.1 connections per site, and
  the live-update stream keeps one open.
- Live updates use server-sent events on `/api/events`. They must not be buffered or compressed:

  | Proxy | What to set |
  |---|---|
  | Nginx Proxy Manager / nginx | Nothing is usually needed: the app sends `X-Accel-Buffering: no`. If updates arrive late, add a custom location `/api/events` with `proxy_http_version 1.1; proxy_set_header Connection ""; proxy_buffering off; gzip off;` |
  | Traefik | Don't attach the `buffering` middleware to this router. If you use `compress`, set `excludedContentTypes: [text/event-stream]` |
  | Caddy | `reverse_proxy` already streams events. If you use `encode`, exclude the stream: `@notsse not path /api/events` then `encode @notsse zstd gzip` |
  | Cloudflare (proxied DNS or Tunnel) | Add a Cache Rule that bypasses `/api/*` |

## 3. Set TRUSTED_PROXIES

The app only trusts the proxy's forwarded headers (the real client address and https) from
addresses you list.

1. Open the app on your phone, sign in, then go to **More → Settings → Connection → Details**.
2. "Your address, as seen" shows the proxy's address while `TRUSTED_PROXIES` is empty.
3. Put that address, or its Docker network (e.g. `172.18.0.0/16`), into `TRUSTED_PROXIES` and
   update the stack.
4. Check again: it should now show your phone's own address.

Never use `*` or `0.0.0.0/0`. The app refuses to start with them.

## 4. First visit

Open the address on a phone:
- **iPhone:** the app first shows how to add it to the home screen. Then open it from the home
  screen and sign in there.
- **Android:** sign in, then use **Install app** from Chrome's menu.

Pick your name under "Who's using this phone?". **Settings** should show the version and
"Live updates: connected".

## Updating

Each release prints these steps:
1. **Stacks → dinner-bell → Editor**. Keep `scopexl/dinner-bell:latest`, or set a specific version.
2. **Update the stack** with **Re-pull image and redeploy** switched on.
3. Wait for **healthy**, then check `<your address>/api/version` shows the new version.

Before migrating, the app copies the database into `/data/backups/pre-migrate/`. If a migration
fails, the app refuses to start and the data is left exactly as it was.

## Backups

- A verified copy is written every night at 03:30 (your `TZ`) into `/data/backups/`, keeping 14
  daily and 8 weekly copies. Settings shows when the last one ran, and **Back up now** makes one
  on demand.
- The copies sit on the same disk as the database. Include the `dinnerbell_data` volume in your
  host's own backups as well.
- To restore, see [RESTORE.md](RESTORE.md).

## Troubleshooting

The container logs explain every refusal in plain words. The exit code says which step failed:

| Exit code | Meaning | Fix |
|---|---|---|
| 78 | A setting is missing or invalid (the log names it, never its value) | Fix the stack variable named in the log |
| 73 | `/data` isn't a mounted volume, isn't writable, is a network filesystem, or another instance is using it | Use the named volume from the example, or `chown -R 10001:10001` the host folder, or set `user:` to the folder's owner. Run exactly one container per volume |
| 74 | Not enough disk space, or the pre-upgrade backup failed | Free disk space and redeploy |
| 65 | The database was upgraded by a newer Dinner Bell than this image | Redeploy the newer version, or restore the pre-upgrade backup (RESTORE.md) |
| 70 | A migration failed. Nothing was changed | Redeploy the previous version and report the log |

Live updates stuck on "connecting", or "checking every 30 seconds"? Your proxy is buffering the
stream: see step 2.
