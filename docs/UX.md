# Dinner Bell — UX

This document covers every screen at phone size, the main flows step by step, empty and quiet states, and the visual direction. It goes with [`PLAN.md`](PLAN.md); the reasoning for design decisions is in [ADR 0012](adr/0012-visual-direction-fridge-door.md).

**The bar:** if a family member has to ask how something works, the design failed. Design for the least technical person, on a phone, in a hurry, standing in an aisle with a cart and weak signal.

## Contents

1. [Rules for every screen](#1-rules-for-every-screen)
2. [Words](#2-words)
3. [Navigation and layout](#3-navigation-and-layout)
4. [Screens](#4-screens)
5. [Flows](#5-flows)
6. [Empty and quiet states](#6-empty-and-quiet-states)
7. [Visual direction: "Fridge door"](#7-visual-direction-fridge-door)
8. [Screenshot review checklist](#8-screenshot-review-checklist)

---

## 1. Rules for every screen

**Reach and touch**
- Primary actions sit in the thumb zone: a bottom action bar above the tabs, or the bottom of a sheet.
- Body text is 16 px, secondary text 14, captions 13 (ADR 0027). Anything a person types into is at least 16 px, so iPhones don't zoom in.
- **Tap targets** (ADR 0027): primary buttons 48 px; other buttons, icon buttons and text links 44 px; chips and two-way switches 40 px; list rows at least 56 px. The shopping checkbox is 48 px inside a 72 × 80 px tap area. Nothing a finger taps is under 40 px; the accessibility tests check it.
- **Every action has a visible button.** Swipes and long-presses are only shortcuts for something already on screen.

**Undo and drafts**
- **Prefer undo over confirmation.** Every destructive action shows an Undo toast for 6 seconds. The one exception is re-sending items to the Kroger cart, which the API can't undo; it uses a confirmation sheet.
- **Nothing is lost by closing the app mid-task.** Drafts save automatically.

**Speed and connection**
- **Taps respond instantly** (optimistic updates); syncing happens behind them.
- **Offline is quiet:** a small pill, never an error wall. Planning screens stay readable offline; editing explains in one line why it waits for a connection.
- **Live:** changes from other phones appear without a refresh.

**What appears on screen**
- **Photos:** Kroger product photos appear wherever an item does. Recognizing a picture beats reading a name. They are never cropped and never covered (§7.5).
- **Never shown:** UPC, SKU, productId or locationId.
- **Empty screens teach.** Each one says what goes there and offers the one button that starts it (§6).

**Theme, accessibility and first run**
- Light and dark themes follow the phone's setting. Text/background pairs meet WCAG AA; a unit test checks the tokens.
- **First run** takes three steps or fewer: choose the store, add a first dinner, done.

## 2. Words

- **Plain words only:** Meals, Sides, Shopping list, Start shopping. No jargon, no abbreviations.
- **Sentence case everywhere;** no all-caps labels.
- **Use the glossary terms** consistently ([PLAN §2](PLAN.md#2-glossary)): Item, Main, Side, Meal, This week's plan, Shopping list, Saved list, Start shopping, Couldn't find, Have it already, Extras, Usuals.
- **A button says exactly what happens**, and the result repeats the same verb. "Save list" leads to "List saved". "Finish trip" leads to "Trip finished".
- **Errors** say what happened and what to do, in the app's voice. They don't apologize and are never vague:
  - "That password didn't match. Try again."
  - "Not saved — you're offline. Try again when you have signal."
- **Money** always reads as an estimate: "About $142". Show "Before tax, fees and tip" on totals. Never show more precision than the estimate deserves. One exception: a meal's price in a card's corner (Plan, Add a meal, the 1440 library) is just "$12", and screen readers hear "about $12".
- **Meta information is stacked on separate lines,** not joined with dots. Aisle info reads "Aisle 12, left side".
- **Attribution names people:** "Added by Mia", "Checked off by Mia".

## 3. Navigation and layout

**Phone (under 1024 px)**
- **Bottom tab bar** with four tabs, each with an icon and a text label: **Plan** (home), **Meals**, **List**, **More**.
- **Shopping mode** is a full-screen mode opened from a big **Start shopping** button. It is not a tab, and it hides the tab bar.
- **Sheets** rise from the bottom for focused tasks: add a meal, amount picker, item details, finish trip. They close with a visible "Done" or "Close" button; swiping down is only a shortcut. A sheet with steps (Add a meal, Add an item) starts each new step at its top, with focus there, so a screen reader doesn't lose its place when the tapped choice goes away.
- **Layout:** 16 px side gutters; safe-area insets respected; no horizontal scrolling.

**Desktop (1024 px and up)** is the same app, responsive; never a separate codebase.
- **Navigation:** a left rail replaces the tab bar.
- **Plan at 1440 px:** three panes side by side: the meal library, this week's plan, and the list summary with its total.
- **Lists and forms** use the extra width for side-by-side detail panes instead of sheets.
- **Print** (from the List screen) uses a print stylesheet: items in aisle order with checkboxes, quantities and sizes; no photos or navigation.

**Installed app (PWA)**
- **Icon, name and splash:** a proper icon, the name "Dinner Bell", and a splash screen.
- **Install guide:** More → Install the app has an illustrated guide for iPhone and Android.
- **iPhone in a normal Safari tab:** the guide appears *before* sign-in (§5.1).

## 4. Screens

Every screen is drawn here at phone size (390×844). The wireframes show structure, not styling.

### 4.1 Sign in

```
+--------------------------------------+
|                                      |
|            [bell mark]               |
|            Dinner Bell               |
|                                      |
|  Household password                  |
|  [............................] [eye]|
|                                      |
|  [            Sign in             ]  |
|                                      |
|  Ask whoever set up Dinner Bell      |
|  for the password.                   |
|                                      |
|  Use a code from another phone       |
+--------------------------------------+
```

- One field with show/hide, and the keyboard's return key submits.
- **Errors:**
  - "That password didn't match. Try again."
  - "Too many tries. Wait 10 minutes."
- **Use a code from another phone** swaps the password for one large field that takes the 8-character code from Add a phone (§5.6), in any case, with or without the space. Below it: "On a phone that's already signed in, open More, then Settings, then Add a phone." **Use the password instead** swaps back.
  - A wrong code: "That code didn't work. A code works once, for 10 minutes. Make a new one on the other phone." Wrong codes count as wrong passwords.
- After sign-in, the phone is remembered for about a year.

### 4.2 Who's using this?

- Big name buttons, one per household member, each in that member's marker color with their initial, plus **Skip**.
- Shopping mode asks again with one tap if the user chose Skip, since check-offs need a name.
- The choice is stored on the server for this device. Change it later in More → Who's using this.

### 4.3 First run (no store chosen yet)

1. **Choose your store.** A ZIP field, then a list of nearby stores (fuel centers removed) with name, address and distance. Tap one.
2. **Add your first dinner.** The guided create flow (§4.8), with Dinner preselected.
3. **"You're set."** One line about what happens next, and the button **See this week's plan**.

### 4.4 Plan (home)

```
+--------------------------------------+
| This week                    [Mia ●] |
|                                      |
| +----------------------------------+ |
| | [ meal photo                   ] | |
| | Tonight                     $12  | |
| | Tacos                            | |
| | with rice and corn            ✎  | |
| +----------------------------------+ |
| +----------------------------------+ |
| |[photo] Chili                $9  | |
| |        with cornbread            | |
| |        [Tue] [×2]             ✎  | |
| |----------------------------------| |
| |[photo] Chicken stir-fry     $11  | |
| |        [Lunch]                ✎  | |
| +----------------------------------+ |
| Uses what you're buying              |
| Taco salad uses your leftover        |
| lettuce, cheese and ground beef.     |
| Adds about $4.                [Add]  |
|                                      |
| [          Add a meal            ]   |
|--------------------------------------|
| About $142          [$11 off on sale]|
| Prices as of 9:14 AM                 |
| Before tax, fees and tip             |
|--------------------------------------|
|  Plan     Meals     List     More    |
+--------------------------------------+
```

- **Tonight card:** shown only when a meal is set for today.
- **Each planned meal** (the Tonight card and every row):
  - its photo (or an item strip);
  - the main, plus "with" its sides;
  - its price in the top-right corner ("$12"; screen readers hear "about $12"), or "No price yet" under the sides;
  - a day chip, if a day is set; a scale chip, if not ×1; what it's for, if not dinner;
  - a small pencil at the bottom right.
- **Tapping anywhere on a meal opens Change** (its button is named "Change Tacos"): how much (×½, ×1, ×2), what it's for, the day, sides; then **Open Tacos** (the meal's page), swap the main, or remove it (with Undo).
- **Uses what you're buying:** up to three Mains that use leftovers of what the list already buys, each with its reason ("Taco salad uses your leftover lettuce, cheese and ground beef. Adds about $4.") and **Add**. Adding puts the Main on the plan without sides, so the total moves by about the amount shown.
- **Each meal's cost:** the meal's share of what it uses, at today's prices and its scale, in the card's corner.
- **Total footer:** sticky; it updates as meals change. When the tally isn't zero, it adds "3 items have no price", which opens the List filtered to those lines.
- **Start a new week** (a quiet button at the end): puts this week's plan away; the toast offers Undo until the new week has meals.
- **At 1440 px:** the meal library (with Add buttons) on the left and the list in walking order on the right.

### 4.5 Add a meal (sheet)

1. **Choose a main.** Every main is listed, with a search box on top that filters as you type. Favorites come first, then the rest alphabetically. Each row shows the photo, name and "about $14". No match: "Nothing matches “xyz”. Try another word."
2. **Eat it for.** Tapping a main moves to its step, which starts with chips for Breakfast, Lunch, Dinner and Snack. The one chosen to begin with is what this main was last planned as, else Dinner (ADR 0026).
3. **Pick a day (optional).** Under "Day", with the choice read out beside it ("Any day", "Today", "Thu, Oct 8"), a short help line: "Optional: the day you'll make it. Each day is the next one coming up, starting today. None picked means any day." Then seven pills, Sun to Sat, with today's marked "today". Tap one to pick it; tap it again to clear it (ADR 0026).
4. **Choose sides.** **Usual sides** first, as large toggles, then **All sides** with search. The bottom of the sheet has **Skip sides** and **Add to plan**.
5. A toast says "Tacos added", with Undo.

### 4.6 Meals (library)

- A **Mains / Sides** switch, a search field, a **Favorites** toggle and an **On sale** toggle (meals using something on sale today). Cards with something on sale show a Sale tag and its last day, beside the text, never on a photo.
- **Cards:**
  - Two per row on phones, more on desktop.
  - Each shows the meal photo (cropped 4:3) or an item strip, the name, "about $14" and a star.
- **New meal** sits in the bottom action bar.
- **Archived meals** are reachable from a "Show archived" link at the end of the list.

### 4.7 Meal detail

- The photo, name, servings, and notes or a recipe link (which opens in a new tab). A meal has no occasion of its own: what it's for is chosen when it's planned (ADR 0026).
- **Items:** one row per item with the product photo, item name, amount ("½ bag", "6 oz", "3") and its share of the cost.
- **Usual sides** (for Mains) are editable: add, remove, pin.
- **Buttons:** **Add to plan** (primary), Edit, Duplicate, Archive (with an Undo toast).

### 4.8 Create or edit a meal (guided; drafts save automatically)

Four steps ("Step 2 of 4"):
1. **Name:** "What do you call it?"
2. **Main or side:** two large buttons, each with a one-line explanation. Tapping one moves straight on.
3. **Items:** "Add an item" opens the add-item flow (§4.9). Each item line shows its photo, name and amount, with Change and Remove.
4. **Anything else? (optional):** a photo (camera or library), servings, and notes or a recipe link.

Then **Save meal** → toast "Meal saved". There's no "When do you eat it?": that's chosen when the meal is planned (ADR 0026). A draft saved before this change picks up at the same step.

### 4.9 Add an item

1. Type a name. The household's own items appear first ("Items you already use").
2. If none fits, Kroger results appear for the chosen store. Each shows:
   - the uncropped product photo;
   - Kroger's description as returned;
   - the size;
   - the price, with a Sale tag beside it when there is one;
   - "Not sold at your store", "Low stock" or "No price" when they apply.
3. Pick one.
   - **A product the household already uses** says "In your items as Shredded cheddar". Picking it is that item again: no copy, so the list never shows twins.
   - **A new product** first asks "What do you call it?", above its photo and facts. The name starts as what was typed, with the last word finished from the product's name ("Shredd" becomes "Shredded"; a trailing space means the word was done). It's editable, and the help line says "This name shows on your list and in your meals." Kroger's description never becomes the name (ADR 0016). "Choose another product" goes back to the results.
   - **Next** (in Extras, **Add to list**) saves the item. The link is remembered for every future meal, and the amount picker opens.
4. **Nothing at your store matches** shows "Add as plain text": an item without a photo or price, labeled "no price".

### 4.10 Amount picker (sheet)

```
+--------------------------------------+
| [product photo]  Shredded cheddar    |
|                  8 oz bag            |
|                                      |
| How much does this meal use?         |
|  [ 1/4 ] [ 1/2 ] [ 3/4 ] [ 1 ] [ 2 ] |
|  Or by weight:  [-]  4 oz  [+] [oz v]|
|                                      |
| About half the 8 oz bag,             |
| about $1.25                          |
|                                      |
| [              Done              ]   |
+--------------------------------------+
```

**Options depend on how the product is sold** ([PLAN §8.7](PLAN.md#87-what-the-amount-picker-offers)). There is never a free-text unit field.

| Package | Picker offers |
|---|---|
| Weight packs | Parts of the package and a weight stepper |
| Volume packs | Parts of the package and kitchen measures (tsp, tbsp, cup) |
| Counts and "each" | A count stepper |
| Sold by the pound | Weight, or a count. For a count, "About how much does one weigh?" is asked once: Small, Medium, Large, 1 lb or Other |
| Size couldn't be read | Parts only, plus **Fix size** |

A live preview line shows the share and the cost.

### 4.11 Shopping list

```
+--------------------------------------+
| Shopping list        [By aisle|meal] |
|                                      |
| +----------------------------------+ |
| | Check the pantry: 6 staples      | |
| | Olive oil     [Have it][Need it] | |
| +----------------------------------+ |
|                                      |
| Produce                              |
| [photo] Yellow onions                |
|         3 onions                     |
|         about $2.10      for Chili   |
| ------------------------------------ |
| Aisle 12, left side                  |
| [photo] Penne pasta                  |
|         2 boxes, 16 oz each          |
|         about $3.98 [Sale] for Tacos |
| ------------------------------------ |
| Extras                               |
| [photo] Milk         Added by Mia    |
| Usuals: [Eggs] [Bread] [Bananas]     |
| [ + Add something else ]             |
|--------------------------------------|
| About $142          [$11 off on sale]|
| [          Save list             ]   |
+--------------------------------------+
```

- **The pantry check** lists the staples (oil, salt, spices…) before saving. Each answers **Have it** or **Need it**. Have-it lines stay visible, lightly marked, and are excluded from the total.
- **Each line shows:**
  - the photo and the item name;
  - the quantity in plain words ("2 boxes", "3 onions", "1.75 lb");
  - the size;
  - the price, with a Sale tag beside it;
  - which meals use it;
  - warnings: "Not sold at your store", "Low stock", "No price".
- **Tapping a line** opens its sheet:
  - a quantity stepper, with a "you added 2" chip;
  - **Have it already**;
  - **Swap product**, listing alternatives with unit prices ("$0.25 per oz"), then **For this trip** or **Always use this**;
  - **Open in Kroger**.
- **Extras:** **Add something else** searches Kroger or takes plain text. The **Usuals** row offers one-tap re-adds of things added before. Every extra shows who added it. Lines no meal uses sit in Extras; an extra on a line a meal uses shows there as "Mia added 1 more".
- **An unlinked item's sheet** offers **Choose a product** instead of Swap product.
- **Bottom bar:**
  - **Save list** freezes the list into a saved list; the toast says "List saved".
  - Once a list is saved, the bar shows **Start shopping**.
  - If the plan changes after that, the bar says "The list changed since you saved it." and offers **Update saved list**: changed lines take the new amounts, new ones are added, and to-do ones no longer needed leave. Whatever was checked off or couldn't be found stays.
  - On desktop it also shows **Print**.

### 4.12 Shopping mode (full screen)

```
+--------------------------------------+
| [Done shopping]          18 of 31    |
| [==============-----------]          |
| [By aisle | By meal]   ● Offline     |
|                                      |
| Produce                              |
| [photo] Yellow onions          [   ] |
|         3 onions                     |
| [photo] Limes                  [   ] |
|         4                            |
| Aisle 12, left side                  |
| [photo] Penne pasta ~~~~~~~~~  [ ✓ ] |
|         Checked off by Mia           |
|                                      |
| > Done (18)                          |
| > Couldn't find (1)                  |
|--------------------------------------|
| In cart about $64 of about $142      |
| [          Finish trip           ]   |
+--------------------------------------+
```

- **Header:**
  - **Done shopping** leaves the mode; the trip stays active.
  - A progress line ("18 of 31") with a thin bar.
  - The **By aisle / By meal** switch.
  - The offline pill, when relevant.
  - A small "Screen stays on" note.
- **Sections** follow the household's walking order. Section headers read "Produce" or "Aisle 12, left side". Within an aisle, items follow shelf order.
- **Each row:** a 64 px product photo tile; the name in bold; the quantity and size ("2 boxes, 16 oz each"); a 48 px checkbox at the right edge, in a 72 px-wide tap column.
- **Checking an item** (tapping the checkbox):
  1. A marker line is drawn through the name in the checker's color (§7.6).
  2. The row slides into the collapsed **Done** group.
  3. A toast says "Checked off Penne pasta", with Undo.
- **Tapping elsewhere on the row** opens big buttons: **Got it**, **Couldn't find**, **Add a note**, **Open in Kroger**.
- **Couldn't find** moves the row to the **Couldn't find** group at the end, where **Try again** puts it back.
- **Footer:** "In cart about $64 of about $142" and **Finish trip**.
- **Get ready for the store:** a card shown when the trip opens. It saves the trip on the phone, saves its photos ("31 of 31 photos saved") and keeps the screen awake, then ends with **Ready for the store**.
- **Another phone finished the trip:** a calm sheet says "Mia finished this trip. Your 3 check-offs were saved." with **Done** and **Reopen**.

### 4.13 Finish trip (sheet)

- "What did you pay? (optional)", with a numeric keypad. Then **Finish trip** → toast "Trip finished" → History.
- Works offline; the trip syncs later and shows a small "will sync" mark.

### 4.14 More

Trips · Settings · Who's using this · Install the app · About and privacy. Each is a full-width row with an icon and a label.

### 4.15 Trips (history)

- **List:** each trip shows the date, store, number of items, and estimate vs. what was paid.
- **Trip detail:** the items and their final states. Buttons:
  - **Shop this again:** a new saved list from the same items, re-priced.
  - **Plan these meals again:** repeat last week.
  - **Reopen.**
  - **Share as text:** the list as plain text, for anyone without the app.

### 4.16 Settings

| Section | Contents |
|---|---|
| Store | Name and address; **Change store** (ZIP search) |
| Store walking order | The section list with up/down buttons per row; a drag handle as a shortcut |
| Household | Members (add, rename, color); household name |
| Kroger account (M5) | Before connecting: one line on what it's for, and **Connect Kroger**. Connected: "Connected", "By Mia", when; **Disconnect** (its toast offers **Connect again**); and "Send lists for" Pickup / Delivery, the default the send sheet starts with. A lemon "Kroger signed Dinner Bell out." banner with **Reconnect Kroger** when Kroger refuses the account. Sample mode adds: "the Kroger sign-in is a demo, and nothing reaches a real cart." |
| Devices | This phone, plus other signed-in devices with "last used"; **Add a phone** (§5.6); **Sign out other devices** |
| Data | **Export all data**; last backup time, and a banner if older than 36 h |
| Connection | "Live updates: connected" (or the quiet polling note); diagnostics for the owner |
| Install the app | The illustrated guide |
| About | Version and build; the not-affiliated note; privacy |

## 5. Flows

### 5.1 First visit on a phone

**iPhone, normal Safari tab**
1. The app opens on the **Install the app** guide, three numbered steps, each beside a small line drawing of the phone with the spot to tap circled in a green marker loop:
   1. Tap **Share**; on newer iPhones, tap ••• next to the address first.
   2. Tap **Add to Home Screen** (scroll down, or tap View More, if it isn't showing), then **Add**.
   3. Open Dinner Bell from the home screen.
2. It explains that the installed app keeps its own sign-in: the household password once more, or a code from a phone that's already signed in (§5.6).
3. **Continue in Safari** is always available.

Android's guide has the same three steps for Chrome: the ⋮ menu, **Install app** (or Add to Home screen) then **Install**, and open it.

**Then, on every phone:**
1. Sign in with the household password.
2. "Who's using this?" → tap your name.
3. If no store is chosen yet, first run (§4.3); otherwise the Plan screen.

### 5.2 Plan a dinner (the success test, part 1)

1. Plan → **Add a meal**.
2. Tap **Tacos** ("Eat it for" starts on Dinner, or on what Tacos was last planned as).
3. Usual sides show first. Tap **Rice**.
4. Optionally tap **Tue**, then **Add to plan**.
5. Back on Plan: Tacos appears, and the total footer updates ("About $38").

### 5.3 Build and save the list

1. **List.** The lines are already merged across meals and rounded up to whole packages.
2. Open **Check the pantry** and mark olive oil **Have it**.
3. Tap **Milk** in Usuals.
4. **Save list** → "List saved". The bottom bar now shows **Start shopping**.

### 5.4 Shop it (the success test, part 2)

1. In the store, tap **Start shopping**. The ready card saves the trip and photos and keeps the screen awake.
2. Walk the aisles in order and tap each checkbox. A marker line crosses the item, and it moves to Done.
3. Can't find something? Tap the row → **Couldn't find**.
4. Changed your mind? **Undo** on the toast, or tap the item in Done.
5. Lose signal? Keep going. The pill says "Offline · saved on this phone", and everything syncs when signal returns. A second shopper's check-offs appear live.
6. **Finish trip**, optionally entering what you paid → "Trip finished".

### 5.5 Send to Kroger cart (M5)

1. Saved list → **Send to Kroger cart**: on the List under Start shopping, or on the trip in Trips. It shows once a Kroger account is connected or can be; without one, the sheet says to connect it in Settings and offers **Go to Settings**.
2. The sheet asks "Pickup or delivery?" (the Settings default chosen) and says: "Items go to the store chosen in your Kroger account. You'll review and check out in the Kroger app."
3. It lists what goes ("Going to your cart") and what can't, under "Add these in the Kroger app": items with no store product ("Not linked to a store product") and pound amounts ("Sold by the pound").
4. **Send 27 items** → "Sending to your Kroger cart: 12 items to go", with a progress bar → "Added 27 items to your Kroger cart."
5. Anything that didn't go is listed first, under "Didn't go", with its reason, and **Send these again** sends only those. If Kroger didn't answer, the row says to look in the Kroger cart before sending it again.
6. Items already sent show under "In your Kroger cart" with "Sent by Mia, 5 minutes ago", and are never sent again by themselves. Opening the sheet again says "Everything here is already in your Kroger cart." **Send again anyway** opens a second sheet, "Send again?", whose buttons are **Send 27 items again** and **Keep my cart as it is**: the one confirmation in the app, because a cart add can't be undone (§1).
7. Every phone with the sheet open follows along while items go out.

### 5.6 Add a phone (M5)

1. On a signed-in phone: More → Settings → **Add a phone**.
2. The sheet shows a QR code, then "Or, on the new phone's sign-in screen, tap Use a code from another phone and type:" and the code in large letters ("4F7K 9QX2"). "It works once, for the next 10 minutes." After 10 minutes: "That code has run out." with **Make a new code**.
3. The new phone scans the code with its camera, which opens Dinner Bell's join page:
   - **Android, a computer, or the installed app:** "Sign in with a code", the code, and **Sign in on this phone** → "Who's using this?"
   - **iPhone in Safari:** "Put Dinner Bell on your home screen first", because the home-screen app keeps its own sign-in. Then: open it, tap **Use a code from another phone**, and type the code (shown again, and still on the other phone). **Show me how** opens the install guide; **Sign in here in Safari instead** stays available.
4. Or, on the new phone's sign-in screen, tap **Use a code from another phone** and type the code.

## 6. Empty and quiet states

| Where | Copy | Button |
|---|---|---|
| Plan | "No meals planned yet. Add a dinner and the shopping list builds itself." | Add a meal |
| Meals | "Your meals live here. Start with a dinner you make often." | New meal |
| Sides | "Sides go with any main. Add rice, a salad, anything you serve alongside." | New side |
| List | "Your list fills in as you plan meals. You can also add things like milk." | Add a meal (+ Add something else) |
| Trips | "Saved lists show up here after you shop." | — |
| Search, no results | "Nothing at your store matches 'xyz'. Try a shorter name, or add it as plain text." | Add as plain text |
| Trip not yet on this phone, while offline | "Open this trip once with signal to save it on this phone." | — |

**Quiet states** are never error walls:

| State | What shows |
|---|---|
| Offline | A small pill: "Offline · saved on this phone" (shopping) or "Updated 2 h ago" (planning) |
| Syncing | "Syncing 3…" |
| Sign-in expired | A tappable "Sign in to sync" |
| Kroger daily limit reached | "Store search is paused until about 3:40 PM — your list still works." |
| Kroger signed Dinner Bell out | A lemon banner in Settings, "Kroger signed Dinner Bell out.", with **Reconnect Kroger**. The send sheet points there too |
| No price on some items | "3 items have no price", which opens the List filtered to those lines |
| Update available | A small "New version · Refresh" pill. Never shown during shopping, and never while changes are waiting to sync |
| Screen can't stay on | A one-time tip: "Your screen may dim while you shop. Settings → Display & Brightness → Auto-Lock" (iPhone) or "Display → Screen timeout" (Android) |

## 7. Visual direction: "Fridge door"

This came out of the frontend-design pass; [ADR 0012](adr/0012-visual-direction-fridge-door.md) has the reasoning.

### 7.1 Concept

The shared list on the fridge door, where everyone in the family writes in their own marker color. It's legible above all, warm without being cute, and grounded in groceries: produce colors, a paper list, a marker.

**The one bold element** is the marker. Checking an item draws a marker line through it in the checker's color, and the same colors show who added an extra or a meal. Everything else stays quiet and disciplined.

### 7.2 Color tokens

Defined once in `frontend/src/styles/tokens.css` (Tailwind v4 `@theme`). Components use tokens only, never raw hex.

| Token | Light | Dark ("night kitchen") | Use |
|---|---|---|---|
| `counter` | `#F3F4F1` | `#1A121E` | App background |
| `paper` | `#FFFFFF` | `#241A29` | Lists, sheets |
| `ink` | `#2B1D30` | `#F3ECF4` | Text (aubergine ink, not black) |
| `ink-soft` | `#5E5163` | `#BFB2C4` | Secondary text |
| `accent` | = `ink` | = `ink` | Primary actions, selected pills, links, progress, focus (ADR 0027). Text on it is `on-accent`: white in light, `#1A121E` in dark |
| `lemon` | `#FFDB3D` | `#FFDB3D` | Sale tags and highlights; text on lemon is always `ink` (light) |
| `tomato` | `#C2381E` | `#FF8266` | Couldn't find, destructive, warnings |
| `rule` | `#DDE1DA` | `#3A2E40` | The ruled lines between list rows |

- **Color comes only from** lemon (the bell and sale tags), tomato (missed, errors, destructive) and the family's marker colors. Actions are ink, so standalone text links and quiet buttons are underlined, and the active tab's icon sits in a filled ink pill.
- **Member marker set:** basil, tomato, carrot, eggplant, beet, olive, cocoa, plum. Each has a light and a dark variant that passes AA as text on `paper`. (Basil the marker is a person's color; actions no longer use green.)
- **Color is never the only signal.** Markers always come with the member's initial or name.
- **No blue anywhere in the identity:** it reads as Kroger's brand color.
- **Contrast is enforced:** a unit test asserts every text/background token pair meets WCAG AA in both themes, and fails the build if not.

### 7.3 Type

- **Typeface:** Atkinson Hyperlegible Next, a self-hosted variable font. It was designed for low-vision legibility, with distinct I/l/1 and 0/O, which is what a glance in an aisle needs. It's the only family.
- **Weights:** 400 (body), 600 (emphasis, row names), 700 (row and section titles), 800 (screen titles, meal names on cards, the total).
- **Sizes** are in rem on the browser's default base (16 px on phones), so a larger default text size scales everything (ADR 0027).

| Role | Size (px) | Line height (px) |
|---|---|---|
| Caption (sparingly, e.g. "Prices as of") | 13 | 18 |
| Secondary | 14 | 20 |
| Body | 16 | 24 |
| Row title | 18 | 24 |
| Screen title | 24 | 30 |
| Total figure | 30 | 36 |

- Prices use tabular figures where the font supports them.
- Sentence case throughout. Reading width is capped at about 72 characters on desktop.

### 7.4 Space, shape and surfaces

- **Spacing:** an 8 px grid with 16 px side gutters, on the browser's default 16 px base. List rows are at least 56 px tall (64 px with a photo).
- **Surfaces:** lists sit on `paper` with ruled `rule` lines between rows, like a notepad. **No grid of identical shadowed cards.** Cards are reserved for things that really are cards (Tonight, recommendations, meal library cards), separated by borders and space rather than soft shadows.
- **Corner radius follows hierarchy:**

  | Element | Radius |
  |---|---|
  | Sheets | 20 px (top corners) |
  | Buttons | 12 px |
  | Photo tiles | 8 px |
  | Chips | fully rounded |

- **Focus:** visible on every control, as a 3 px `accent` (ink) outline with a 2 px offset; on inverse surfaces (toasts, prompts) the ring is the `counter` color.

### 7.5 Images

**Kroger product photos**
- Drawn only by the `ProductImage` component: a **white tile** (white in dark mode too, like a label), with the photo inside at `object-fit: contain`.
- **Never cropped, filtered, dimmed or overlaid.** Badges such as Sale sit *beside* the tile, never on it.
- The tile's box has rounded corners; the image itself is never clipped.
- On Done rows, only the text dims.

**Household meal photos**
- May be cropped to 4:3 on cards and to the Tonight banner.
- A meal without a photo shows a strip of up to three of its item tiles (uncropped) on `paper`. Never stock imagery.

### 7.6 Motion

- **The signature moment:**
  1. A slightly wobbly marker stroke (SVG path, randomized per row within a small range) draws left to right through the item name in 250 ms, in the checker's color.
  2. The row then slides into Done (200 ms).
- **Other motion only answers an action** (sheets opening, a toast appearing, a list reordering) and shows what changed. No decorative entrance animations.
- **`prefers-reduced-motion`:** the strike appears instantly, and rows move without sliding.

### 7.7 Icons and app icon

- **lucide icons**, 2 px stroke, always next to a text label on primary actions and tabs.
- **App icon:** a bell drawn as a marker stroke in `ink` on `lemon`. It's maskable (safe zone respected). No blue, and no oval or anything resembling Kroger's logo. The splash screen uses the same mark.

### 7.8 Design self-critique (what changed after review)

The first pass was checked against the generic look such a brief tends to produce, and revised:

| First pass | Changed to | Why |
|---|---|---|
| A serif display face for titles | A single family | Cream + serif + terracotta is the default "warm food app" look; one highly legible family serves the aisle better |
| Blue in the palette | None | Too close to Kroger's brand color, which the branding rules forbid |
| A grid of shadowed cards | Ruled paper lists | Cards are kept only where something really is a card |
| Meta strings joined with "·" | Stacked lines | Easier to scan at a glance |
| Several entrance animations | One signature motion (the marker strike) | Other motion only answers actions |

## 8. Screenshot review checklist

Run `just screenshots` after every UI change. It captures the key screens in fake mode at 390×844 and 1440×900, in light and dark. Then check each screenshot:

- [ ] The primary action is reachable with a thumb, and nothing important hides under the tab bar or the home indicator.
- [ ] Body text is 16 px (secondary 14, captions 13), typing fields at least 16 px, and nothing is truncated that matters (long meal names wrap).
- [ ] Product photos are uncropped, nothing covers them, and Sale tags sit beside them.
- [ ] No internal IDs, no jargon, no all-caps labels, no "A · B · C" meta strings.
- [ ] Empty states say what goes there and offer one button.
- [ ] Contrast holds in dark mode, and the tokens are used (no stray colors).
- [ ] Touch targets are at least 40 px (buttons 44–48 px, the shopping checkbox 48 px).
- [ ] Desktop uses the width (panes), with nothing stretched across 1440 px.
- [ ] Nothing in the screenshots comes from real household data. Fake mode only; screenshots stay in `.screenshots/`, which is gitignored.
