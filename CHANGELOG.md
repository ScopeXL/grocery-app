# Changelog

Everything that changes in Dinner Bell, written in plain English. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Rename an item from its amount picker or from its line on the shopping list. The new name shows
  in your meals and on this week's list, and Undo puts the old one back.

### Changed

- Text is smaller and crisper, and buttons, pills and rows take less room, so screens fit more.
  Everything is still easy to tap: nothing is under 40 px, and shopping's checkboxes stay big.
- The green is gone: buttons, links and selected choices are a dark ink, so sale tags and each
  person's color stand out.
- A meal's day is picked from Sunday-to-Saturday pills, with a line explaining them: each is the
  next such day, starting today. Tap it again to clear it; none picked means any day.
- Add a meal lists every meal, with a search box on top. After you pick one, choose what it's for
  (breakfast, lunch, dinner or a snack): it starts on whatever that meal was last planned as.
- Making a meal no longer asks "When do you eat it?", and Meals no longer filters by it: what a
  meal is for is chosen when you plan it.
- Plan's meals are tidier: tap anywhere on one to change it. Its price sits in the corner, and the
  Change sheet has a link to open the meal.
- "Who's using this phone?" shows who's using it now, with a check, and goes back to where you
  opened it. More shows the name too.

### Fixed

- Picking a store product before you finish typing no longer names the item with half a word
  ("Shredd"). You now name it first: the name starts with your last word finished ("Shredded"),
  and you can change it. Picking a product you already use adds that item again instead of a
  copy.
- Undo works while a sheet is open: its message used to sit behind the sheet, out of reach.
- In dark mode, Undo and Refresh on the messages at the bottom of the screen are readable again.
- The bar above the tabs no longer tucks slightly under them.

## [0.6.0] - 2026-10-07

### Added

- Send a saved list straight to your Kroger cart, for pickup or delivery, then check out in
  the Kroger app. Connect your Kroger account once in Settings. Each item goes once; anything
  that didn't go can be sent again on its own; items sold by the pound are listed for you to
  add in the Kroger app.
- Add a phone without the password: Settings shows a QR code to scan, or a code to type on the
  new phone's sign-in screen. On an iPhone it works in the home-screen app too.
- The install guide shows a drawing for each step on iPhone and Android, including the newer
  iPhone Safari layout.

### Changed

- The first-run guide ends on this week's plan.
- About & privacy explains what connecting a Kroger account means.

### Fixed

- Screen readers announce the Mains and Sides switch correctly, and long sheets scroll with a
  keyboard.

### Behind the scenes

- Every main screen is checked for accessibility problems in light and dark; Kroger's sign-in
  is stored encrypted and renewed by itself.

## [0.5.0] - 2026-10-07

### Added

- Plan suggests up to three meals that use what you're already buying, with the reason in
  plain words, like "Taco salad uses your leftover lettuce, cheese and ground beef. Adds about
  $4." Tap Add and the total moves by about that much.
- Each planned meal shows what it costs at today's prices.
- Sale tags say when the sale ends, and Meals has an On sale filter.

### Behind the scenes

- The suggestions are checked against worked examples, so the amount a suggestion says it adds
  is what the total really moves by.

## [0.4.0] - 2026-10-06

### Added

- Save list turns this week's list into a saved list to shop from. If the plan changes, Update
  saved list brings it up to date without losing what's already checked off.
- Shopping mode: the list in your store's walking order (or by meal), big checkboxes, a marker
  line through each item in your color, Couldn't find, notes, Undo, and a running total of
  what's in the cart.
- It works with no signal. The list and its photos are saved on your phone before you go, and
  check-offs sync as soon as there's signal again.
- Two people can shop the same list and see each other's check-offs as they happen.
- Finish the trip with what you paid. Trips keeps your history: shop a list again at today's
  prices, plan those meals again, or reopen a trip.
- Share a list as text with anyone who doesn't have the app.
- Store walking order in Settings: put the store's sections in the order you walk them.
- The screen stays on while you shop.

### Behind the scenes

- Every tap in the store is saved on the phone first and sent exactly once, even when two
  phones disagree or a phone's clock is off; a finished trip's copy of Kroger's photos and
  aisles is cleared a day later.

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

[0.3.0]: https://github.com/ScopeXL/grocery-app/compare/v0.2.0...v0.3.0

[0.4.0]: https://github.com/ScopeXL/grocery-app/compare/v0.3.0...v0.4.0

[0.5.0]: https://github.com/ScopeXL/grocery-app/compare/v0.4.0...v0.5.0

[Unreleased]: https://github.com/ScopeXL/grocery-app/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/ScopeXL/grocery-app/compare/v0.5.0...v0.6.0
