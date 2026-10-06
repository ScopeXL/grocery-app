# ADR 0017: Privacy guardrails: gitleaks, a local private-terms scan, synthetic fixtures

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The repository and the Docker image are public. Household-specific values must never land in git or the image:
- names and addresses;
- ZIP codes and store IDs;
- domains, hostnames and IPs;
- tokens;
- screenshots of real data.

A leak is a release-blocking bug. Generic secret scanners catch keys and tokens, but not a household's ZIP code or a family member's name. Those can't be listed in a public config file either.

## Decision

**What the scans run**
- **gitleaks** (default rules, plus custom ones for Docker Hub tokens, non-placeholder app secrets, Fernet tokens and session cookies) runs in three places:
  - the repo-managed git hooks (`.githooks/`, installed by `just setup`);
  - CI;
  - `just preflight` before every release.
- **A local private-terms list** at `~/.config/dinner-bell/private-terms.txt` lives outside the repo, the build context and the working directory, and is never committed. `just setup` prompts for each category: ZIP, store ID, member names, street, domain, host and IP, LAN range, the build Mac's username and home path, and emails.
- **`scripts/private_scan.py`** matches those terms against:
  - staged diffs;
  - commit messages and author fields;
  - push ranges and full history;
  - the `git archive` build context;
  - the published image's labels, env and history.

  It prints `term #n`, never the term itself. A missing or empty list fails `scan` and `preflight`. The MIT copyright line and the configured git author name are explicitly allowed.

**What keeps private data out by design**
- **Image build:** images are built from `git archive` of a tag (ADR 0005), so untracked files can never enter one.
- **Fixtures** are synthetic: "Sample Whole Milk", `99999001`, "Sample Parent".
- **Screenshots** come only from fake mode and go only to the gitignored `.screenshots/`.
- **Configuration:**
  - `.env` is gitignored and `.dockerignore` is an allowlist.
  - `.claude/settings.json` denies AI sessions read access to `.env` and private folders.
- **Commits** use the GitHub noreply identity (ADR 0022).
- **GitHub settings:** secret scanning and push protection stay on, alongside Dependabot alerts and private vulnerability reporting.

## Consequences

- Every contributor, human or AI, gets automatic protection, provided they run `just setup` and keep the private-terms list current.
- The private-terms scan can't run in CI, because the list never leaves the owner's machine. Preflight is therefore mandatory before any release.
