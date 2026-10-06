# ADR 0005: Release images built locally with buildx, for amd64 and arm64

- **Status:** Accepted (the owner's answers to the open questions)
- **Date:** 2026-10-06

## Context

- The Portainer host is **amd64**. The development Mac is Apple Silicon, so a plain local build would produce arm64 only.
- The owner chose **local buildx** over a GitHub Actions build. The reference apps publish no images at all, so there was nothing to mirror.
- OrbStack is installed on the build Mac. It provides the docker CLI, buildx 0.33 and the containerd image store, which can build and push multi-platform images.

## Decision

- **Build from git, not the working tree.** `git archive <tag> | docker buildx build --builder orbstack -`. Untracked `.env` files, screenshots and private lists can never reach an image, and each image matches its tag exactly.
- **Platforms:** `linux/amd64` and `linux/arm64`. arm64 is native on the Mac and cheap to build, and the repo is public, so others may run ARM hosts.
- **The frontend stage** builds once on `$BUILDPLATFORM`.
- **Name and tags:** `scopexl/dinner-bell`, tagged `X.Y.Z`, `X.Y` and `latest`. Turn on Docker Hub's immutable-tag rule for `^\d+\.\d+\.\d+$`.
- **Before pushing,** `just smoke-image` builds amd64, runs it and probes health, version, the SPA fallback, 404s and the non-root uid. It also checks that the startup checks refuse a root-owned volume and a missing volume.
- **After pushing,** `just image-verify` confirms the manifest lists exactly both platforms and that the tags agree. It then pulls the published amd64 digest, re-runs the probes, and scans the image's labels, env and history for private terms.
- **CI.** GitHub Actions runs checks only (lint, types, tests, e2e, gitleaks) and has no secrets. Images are never built there.
- **Login.** Docker Hub login uses a personal access token typed at the prompt and kept in the macOS keychain, never in the repo.

## Consequences

- Releases depend on the owner's Mac (with OrbStack running). The `just release` recipe documents the whole path, so a Mac without Claude can release too.
- amd64 builds run under Rosetta on the Mac. That's fast enough here, because the only target-specific step is installing Python wheels.
- A GitHub Actions build workflow (`workflow_dispatch`) can be added later as a fallback, if the Mac becomes a bottleneck.
