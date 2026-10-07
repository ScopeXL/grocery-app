# ADR 0026: What a meal is for is chosen when planning it; days are Sunday-to-Saturday pills

- **Status:** Accepted (the owner's choices after a week of use, 2026-10-07). Supersedes the occasion part of ADR 0006.
- **Date:** 2026-10-07

## Context

ADR 0006 made occasions (breakfast, lunch, dinner, snack) tags on each meal, and also on each planned meal. Creating a meal asked "When do you eat it?", and Add a meal filtered by it, with Dinner preselected.

In use, that was wrong in two ways:
- **It doesn't belong to the meal.** Taco salad is a lunch one week and a dinner the next.
- **It hid meals.** Add a meal opened on Dinner, so a meal tagged only as lunch wasn't shown until someone thought to tap Lunch.

Days were "Any day, Today", then the next six days by name. The owner wanted the standard week instead.

## Decision

**What a meal is for**
- **Meals carry no occasion.** Creating or editing a meal no longer asks.
- **It is chosen when a meal is planned.** Add a meal lists every main, with a search box on top. After picking one, "Eat it for" offers Breakfast, Lunch, Dinner or Snack. Change offers the same.
- **The starting choice is whatever that main was last planned as, otherwise Dinner.**
  - It is read from the plan history (`plan_meals`): meals removed from a plan don't count, and past weeks do.
  - A plan without an occasion (a one-tap suggestion) gets the same default from the server.
- **The `dishes.occasions` column stays in the database, unused.** That needs no migration, and an older image rolled back onto this database still works.
  - For one release, dish responses keep a deprecated `occasions` field that lists all four occasions. Phones still on the old build read it until someone taps Refresh, and this way they see every meal and don't crash.
  - It is removed in the following release.

**Days**
- **Seven pills, Sun to Sat,** in that order. Each is the next such day, today included, and today's pill is marked.
- **Tapping the chosen pill clears it; none chosen means any day.** A help line says so.
- **One day per meal.** A meal eaten twice is planned twice.

## Considered and not chosen

- **Several days per meal** (picking Tue and Thu adds the meal twice): harder to undo and explain, for little gain.
- **Keeping the meal's tags as a hint:** the plan history already says what a meal is usually for, without asking.

## Consequences

- Making a meal takes one step fewer. Add a meal shows every meal at once.
- The Plan's "Tonight" card still means a dinner on today's date.
- The deprecated field must be removed in the next release (PLAN §15).
