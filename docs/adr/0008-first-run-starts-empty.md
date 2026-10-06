# ADR 0008: Start empty, with a guided first dinner

- **Status:** Accepted (the owner's answer to the open question)
- **Date:** 2026-10-06

## Context

The alternative was a few sample meals (tacos, spaghetti…). Sample data has three problems:
- It has to be deleted.
- It can't be linked to the household's store products without a matching step the household would need to review.
- It hides the empty states that teach the app.

## Decision

The app starts empty. First run takes three steps or fewer:
1. Choose your store by ZIP.
2. Add your first dinner, using the guided create flow with Dinner preselected.
3. "You're set" → the Plan screen.

Every empty screen says what goes there and offers the one button that starts it ([UX §6](../UX.md#6-empty-and-quiet-states)).

## Consequences

- The first session takes a few minutes of setup by whoever plans meals. Everyone after that sees real household data.
- A basic first run ships in M1; it is polished in M5.
