# Changelog

Everything that changes in Dinner Bell, written in plain English. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

- Sturdier releases: they check GitHub access before starting, can resume after a failed upload,
  and the privacy check now also reads release tags.
- Kroger's product details are used live and kept only as long as Kroger allows.

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

[Unreleased]: https://github.com/ScopeXL/grocery-app/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ScopeXL/grocery-app/releases/tag/v0.1.0
