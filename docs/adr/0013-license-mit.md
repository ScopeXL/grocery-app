# ADR 0013: MIT license

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The brief asked which license to use before the first public push, defaulting to MIT. The repository's first commit already contains an MIT `LICENSE`, committed by the owner.

## Decision

The project is MIT-licensed, as already committed.

## Consequences

- Others may deploy and modify the app. That's why nothing household-specific may ever be committed (ADR 0017), and why the app enforces its own login (ADR 0003).
- The copyright line in `LICENSE` is an intended public identity, so the private-terms scan explicitly allows it.
