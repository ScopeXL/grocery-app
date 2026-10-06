# ADR 0011: The app is called Dinner Bell

- **Status:** Accepted (the owner's answer to the open question)
- **Date:** 2026-10-06

## Context

Kroger's branding rules say an app can't have "Kroger" anywhere in its name, can't sound similar, and can't imply endorsement. The name should be:
- plain;
- warm;
- dinner-first;
- short enough to fit under a home-screen icon (about 12 characters).

The candidates were Dinner Bell, Fridge List and Weeknight.

## Decision

The app is **Dinner Bell**:

| Where | Name |
|---|---|
| App display name | Dinner Bell |
| Python package | `dinnerbell` |
| Docker image | `scopexl/dinner-bell` |
| Repository | stays `grocery-app` |

The README and the in-app About page carry this note: "Dinner Bell is an independent project and is not affiliated with, endorsed by, or sponsored by The Kroger Co."

## Consequences

- The name has nothing to do with Kroger, which keeps it clear of the branding rules.
- The icon is a marker-drawn bell (see ADR 0012). It uses no Kroger blue and no oval.
