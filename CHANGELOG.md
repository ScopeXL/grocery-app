# Changelog

Everything that changes in Dinner Bell, written in plain English. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Behind the scenes

- Sturdier releases: they check GitHub access before starting, can resume after a failed upload,
  and the privacy check now also reads release tags.

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
