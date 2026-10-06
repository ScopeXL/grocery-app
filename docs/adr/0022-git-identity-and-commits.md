# ADR 0022: Noreply commit identity; commit when green; push only on deploy

- **Status:** Accepted (the owner's answers)
- **Date:** 2026-10-06

## Context

The repo is public, and commit metadata is public too. Its first commit was authored with a personal email address, and the machine's default git email is on a personal domain. AI sessions will make most of the changes here, so the commit habit has to be explicit.

## Decision

**Identity**
- This repository sets its own git email to the owner's GitHub noreply address.
- The owner turns on GitHub's "Keep my email addresses private" and "Block command line pushes that expose my email".
- The first commit stays as it is: it's already public, and rewriting it would need a force-push.
- The private-terms scan checks author and committer fields on every push.

**Commits**
- AI sessions commit after each finished unit of work that passes `just check`.
- Subjects follow `area: summary`, for example `planning: merge extras into the list`, and carry the Co-Authored-By trailer.
- Stage explicit paths. Never `git add -A`, and never stash or discard someone else's changes.

**Pushes**
- Nothing is pushed except by the deploy skill (ADR 0005, PLAN §11.10), or when the owner asks.

## Consequences

- Work is recoverable and reviewable commit by commit, without anything reaching GitHub before the owner has seen it.
- CI runs only when something is pushed, so `just check` before each commit is the local guarantee.
