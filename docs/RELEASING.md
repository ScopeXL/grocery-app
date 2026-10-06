# Releasing

The owner says **deploy**; the `deploy` skill ([`.claude/skills/deploy/SKILL.md`](../.claude/skills/deploy/SKILL.md))
does the rest. This page explains the pieces, and how to release without Claude.

## What a release is

- A version bump in `VERSION`: patch by default, minor when users can see something new, major
  only when the owner asks. Each milestone is a minor release.
- A plain-English `CHANGELOG.md` section.
- An annotated git tag `vX.Y.Z` that is never moved.
- A multi-arch image (`linux/amd64`, `linux/arm64`), `scopexl/dinner-bell:X.Y.Z`, also tagged
  `X.Y` and `latest`. Version tags are immutable on Docker Hub.

## The pipeline

| Step | Command | Stops the release when |
|---|---|---|
| Gate | `just preflight` | Not on main, uncommitted changes, behind origin, a dry-run push to GitHub fails, any check/e2e/scan failure, smoke-test failure, Docker not ready |
| Version | `just bump <level>` | `[Unreleased]` is empty |
| Tag | `just release-tag ["Co-Authored-By: …"]` | Anything besides `VERSION`, `CHANGELOG.md` and `released.lock` changed since preflight. If only the push fails, run it again: it resumes |
| Smoke | `just smoke-image vX.Y.Z` | The image from the tag doesn't start healthy, fails a probe, or starts on a bad volume |
| Push | `just image` | The version already exists on Docker Hub |
| Verify | `just image-verify` | Platforms missing, tags disagree, the pulled image fails a probe, or the image scan finds a private term |

Without Claude: `just release patch` runs all of it.

## One-time setup on the build Mac

- **OrbStack** running, with Docker on its context (`docker context use orbstack`) and the
  containerd image store.
- **Docker Hub:**
  1. In Docker Hub, create a personal access token: Read & Write, no Delete, with an expiry.
  2. Run `docker login -u scopexl` and paste the token at the prompt. It's kept in the macOS
     keychain, never in a file in this repo.
  3. In Docker Hub: **Repository → Settings → Immutable tags**, with the rule `^\d+\.\d+\.\d+$`.
- **Private-terms list:** `just setup` walks you through creating
  `~/.config/dinner-bell/private-terms.txt`. Preflight refuses to release without it.
- **GitHub:** pushes go over SSH; see *Pushing to GitHub* below.

## Pushing to GitHub

A release pushes without a terminal, so git must reach GitHub without asking for a password.
Preflight checks this with a dry-run push before anything is tagged.

- This repo's remote uses SSH: `git remote get-url origin` shows
  `git@github.com:ScopeXL/grocery-app.git`, and `ssh -T git@github.com` answers
  "Hi <your GitHub name>!".
- To switch a clone that uses HTTPS, run
  `git remote set-url origin git@github.com:ScopeXL/grocery-app.git`.
- An HTTPS remote works only with a saved login whose token has the `workflow` scope, because
  releases include `.github/workflows/`.
- If a release's push fails anyway, the release commit and tag stay on this Mac. Fix access, then
  run `just release-tag` again: it pushes them without re-tagging.

## Rolling back

- **If the release didn't change the database** (no new migration), redeploy the previous tag
  in Portainer.
- **If it did,** restore the pre-upgrade copy ([RESTORE.md](RESTORE.md)), then deploy the
  previous tag.

Migrations are forward-only ([ADR 0021](adr/0021-forward-only-migrations.md)).
