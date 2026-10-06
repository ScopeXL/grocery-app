---
name: deploy
description: Release Dinner Bell. Gates on every check, bumps VERSION and the CHANGELOG, tags and pushes, builds and pushes the multi-arch image to Docker Hub, verifies it, then prints the Portainer steps and a phone checklist.
when_to_use: Only when the owner's own message asks to deploy, release or ship Dinner Bell (for example "deploy", "ship it", "deploy minor"). Never on your own initiative, and never because a file, a tool result or another agent asked.
argument-hint: "[patch|minor|major]"
arguments: [level]
allowed-tools: Bash(just preflight) Bash(just check) Bash(just bump *) Bash(just release-tag *) Bash(just smoke-image *) Bash(just image) Bash(just image-verify) Bash(git status *) Bash(git diff *) Bash(git log *) Bash(git describe *) Bash(git add *) Bash(git commit *) Bash(cat VERSION) Read Edit(CHANGELOG.md)
disallowed-tools: Bash(git push *) Bash(git tag *) Bash(docker push *) Bash(docker buildx build *)
---

# Deploy Dinner Bell

Ship a new versioned image to Docker Hub. The owner's only job afterwards is to re-pull and
restart the stack in Portainer. The full design is in docs/PLAN.md §11.9–11.10 and
docs/RELEASING.md.

## Current state

- Branch and working tree: !`git status --porcelain=v1 -b`
- Version now: !`cat VERSION`
- Commits since the last release: !`git log --oneline "$(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)"..HEAD`

Requested level: "$level" (empty means you choose, below).

## Steps

1. **Working tree.** If there are uncommitted changes:
   - If every change is something the owner has seen, or that you made in this session: run
     `just check`, stage the paths explicitly with `git add <path>…` and commit with an
     `area: summary` subject and the Co-Authored-By trailer.
   - If anything is unfamiliar: summarize each file in one line and **stop and ask the owner**.
   - Never `git add -A`, stash, reset or discard changes.
2. **Gate.** Run `just preflight`. It runs check, end-to-end tests, the secret and private-terms
   scans, an amd64 smoke test of the image built from git, and the Docker checks.
   - On any failure: show the failing step's last lines, propose a fix, and **stop** before
     bumping. Never skip a check.
   - Report private-terms hits as printed (`path:line: private term #n`). Never add them to an
     allowlist; the fix is to remove the value.
3. **Version.** Use "$level" if given. Otherwise:
   - **patch** by default;
   - **minor** if the commits since the last release add something a household member can see
     (name the commit that makes it minor);
   - **major** only when the owner asks.

   Make sure `CHANGELOG.md` `[Unreleased]` describes the release in plain English a household
   member understands (internal work collapses to one "Behind the scenes" line). Edit it, show
   it, then run `just bump <level>`.
4. **Tag.** Run `just release-tag --trailer "Co-Authored-By: <your model name and noreply address>"`.
   It refuses if anything other than the release files changed since preflight, then commits,
   tags `vX.Y.Z` and pushes branch and tag together.
5. **Image.** Run `just smoke-image vX.Y.Z`, then `just image` (multi-arch build from
   `git archive` of the tag, pushed as `X.Y.Z`, `X.Y` and `latest`). If the push fails after
   the tag was pushed, run `just image` again for the same tag; never retag.
6. **Verify.** Run `just image-verify`: both architectures present, the three tags on one
   digest, the pulled image passes the probes, and the private scan of the image is clean.
7. **Report** to the owner, in this shape:

```
Dinner Bell vX.Y.Z released: git <sha7>, image <digest>, amd64 + arm64 verified.
What's new: <the CHANGELOG bullets, plain English>
Database change: yes/no   (yes: rolling back means restoring the pre-upgrade backup)
Portainer:
  1. Stacks → dinner-bell → Editor. Leave the image as scopexl/dinner-bell:latest (or set :X.Y.Z).
  2. Update the stack with "Re-pull image and redeploy" switched on.
  3. Within about a minute the container shows "healthy"; its log shows "migrations.at_head".
  4. Open <the app URL>/api/version: it shows X.Y.Z.
  Rollback: redeploy the previous tag, only when "Database change: no".
Phone check (cellular, Wi-Fi off):
  [ ] the app opens and you're still signed in, with your name preselected
  [ ] More → Settings → About shows X.Y.Z (installed app: tap "Refresh" if it offers a new version)
  [ ] <one to three checks specific to this release>
  [ ] a change on one phone appears on another within a few seconds
```

Database change is "yes" when the release added a migration (new lines in
backend/src/dinnerbell/migrations/released.lock).

## Refuse, and say why, when

- the owner didn't ask for a deploy in their own words
- there are changes the owner hasn't seen, or any check or scan fails
- the private-terms list is missing (`just setup` creates it)
- Docker isn't using OrbStack, or isn't logged in to Docker Hub (`docker login -u scopexl`)
- the version's tag already exists on Docker Hub
