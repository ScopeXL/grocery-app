# Changelog

Everything that changes in Dinner Bell, written in plain English. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-10-06

### Added

- Plan the week: add Mains with their Sides, set a day or leave it for any day, and make a
  meal half or double. Tonight's dinner shows first.
- Usual sides: Dinner Bell learns which Sides go with each Main, and you can change them.
- The shopping list builds itself from the plan. What every meal needs is added up, then
  rounded to whole packages once, grouped by aisle or by meal, with prices and sale tags.
- The total at the bottom of Plan and List: what sales save, when prices were checked, and
  which items have no price.
- Check the pantry: staples like oil ask "Have it?" before they count toward the total.
- Change how many to buy, or swap a product for this trip or for good, comparing prices per
  ounce.
- Extras like milk, from your store or as plain text, show who added them, and Usuals put back
  what you add often in one tap.
- Start a new week, with Undo. On a computer, see your meals, the plan and the list side by
  side, and print the list in aisle order.
- Plan changes appear on every phone within seconds.

### Behind the scenes

- Hundreds of new checks that the list's amounts and total are right, and that upgrading keeps
  every meal and item you've made.

## [0.2.0] - 2026-10-06

### Added

- Choose your store by ZIP code, in a short first-run guide or later in Settings.
- Make Mains and Sides step by step. A half-made meal is saved on your phone as you go.
- Add what a meal needs from your store, with Kroger's photos, sizes and prices, or as plain
  text.
- Say how much a meal uses: part of a package, a weight, a kitchen measure or a count. A preview
  shows what that means, like "About half the 8 oz bag" and "about $1.25".
- Each meal shows what it costs at today's prices, and each item its share.
- Meal photos, favorites, Duplicate, and Archive with Undo.

### Behind the scenes

- Sturdier releases and privacy checks; Kroger's product details are fetched live and never
  stored, as Kroger's terms require.

## [0.1.0] - 2026-10-06

### Added

- Sign in with the household password. Each phone stays signed in for a year.
- "Who's using this phone?", so the family can see who added or checked off what.
- On iPhone, a short guide to putting Dinner Bell on the home screen, shown before signing in.
- The Plan, Meals, List and More tabs. Adding meals arrives in the next update.
- Settings: household members, signed-in devices (with "Sign out other devices"), export all
  data, backups, connection details and the version.
- Changes made on one phone appear on the others within seconds.
- The app opens without signal once it has been used, and says so quietly.
- A verified backup every night, and another before every upgrade.

### Behind the scenes

- The first server, database, release pipeline and privacy checks.

[0.1.0]: https://github.com/ScopeXL/grocery-app/releases/tag/v0.1.0

[0.2.0]: https://github.com/ScopeXL/grocery-app/compare/v0.1.0...v0.2.0

[Unreleased]: https://github.com/ScopeXL/grocery-app/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ScopeXL/grocery-app/compare/v0.2.0...v0.3.0
