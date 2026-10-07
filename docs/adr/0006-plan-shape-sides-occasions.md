# ADR 0006: The plan is a list with optional days; usual sides are learned; occasions are tags

- **Status:** Accepted (the owner's answers to the open questions); its occasion part is superseded by ADR 0026
- **Date:** 2026-10-06

## Context

Planning dinners is the main job, and breakfast, lunch and snacks are secondary. Two shapes were considered:
- **A Monday–Sunday calendar:** clear structure, but empty slots nag, and changing plans means moving meals around.
- **A list:** fewer rules to learn.

Sides could be auto-added as hand-set defaults, or suggested.

## Decision

- **This week's plan is a list of meals.** Any meal can be pinned to a day. The Plan screen shows a **Tonight** card when a meal is set for today.
- **Usual sides are suggested, never auto-added.** Adding a Main opens a sheet with that Main's usual sides first, then all sides, with **Skip** always available.
  - Usual sides are learned from what the household picks (`dish_pairings.times_chosen`).
  - They can be edited by hand: pin or hide.
- **Occasions are tags** on the same dishes and planned meals: Dinner, Breakfast, Lunch, Snack. A dish can have several. Dinner is preselected everywhere. There's one library and one flow.

## Consequences

- No calendar grid to build or learn. "Tonight" covers the main time-based need.
- Nothing lands on the list without a tap, so there are no surprise items.
- Filtering by occasion is a chip, not a separate section, so breakfasts don't need their own screens.
