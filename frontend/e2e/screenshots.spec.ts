/**
 * Captures the key screens for review (`just screenshots`): phone and desktop, light and dark.
 * Fake mode only; files go to the gitignored .screenshots/ folder (CLAUDE.md rule 1).
 */
import type { Page } from "@playwright/test";

import { expect, signIn, test } from "./fixtures";

const CSRF = { "X-Dinner-Bell": "1" };

/** Scroll through once so lazy photos load, then wait for every photo before capturing. */
async function settle(page: Page): Promise<void> {
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForFunction(() => Array.from(document.images).every((image) => image.complete));
}

/** A few synthetic meals so the library, detail and editor have something to show. */
async function seedMeals(page: Page): Promise<{ tacos: string; chicken: string; rice: string }> {
  const item = async (name: string, product_id: string) => {
    const response = await page.request.post("/api/items", {
      data: { name, product_id },
      headers: CSRF,
    });
    return ((await response.json()) as { id: string }).id;
  };
  const line = (item_id: string, kind: string, value: string, unit: string | null = null) => ({
    item_id,
    amount: { kind, value, unit },
  });
  const dish = async (body: Record<string, unknown>) => {
    const response = await page.request.post("/api/dishes", {
      data: { favorite: false, ...body },
      headers: CSRF,
    });
    return ((await response.json()) as { id: string }).id;
  };
  const cheddar = await item("Shredded cheddar", "0000000000002");
  const beef = await item("Ground beef", "0000000000003");
  const tortillas = await item("Tortillas", "0000000000005");
  const salsa = await item("Salsa", "0000000000008");
  const rice = await item("White rice", "0000000000007");
  const thighs = await item("Chicken thighs", "0000000000014");
  const tacos = await dish({
    name: "Tacos",
    role: "main",
    favorite: true,
    servings: 4,
    notes: "Warm the tortillas in a dry pan.",
    lines: [
      line(beef, "measure", "1", "lb"),
      line(tortillas, "count", "8"),
      line(cheddar, "packages", "1/2"),
      line(salsa, "packages", "1/2"),
    ],
  });
  const chicken = await dish({
    name: "Sheet-pan chicken",
    role: "main",
    lines: [line(thighs, "measure", "2", "lb"), line(rice, "packages", "1/4")],
  });
  const riceSide = await dish({
    name: "Rice",
    role: "side",
    lines: [line(rice, "packages", "1/4")],
  });
  // Shares Tacos' beef, cheddar and salsa: Plan suggests it once Tacos is planned.
  await dish({
    name: "Taco salad",
    role: "main",
    lines: [
      line(beef, "packages", "1/2"),
      line(cheddar, "packages", "1/2"),
      line(salsa, "packages", "1/2"),
    ],
  });
  return { tacos, chicken, rice: riceSide };
}

/** This week: Tacos with Rice tonight, the chicken twice over, a staple and an extra. */
async function seedPlan(page: Page, meals: { tacos: string; chicken: string; rice: string }) {
  const post = async (path: string, data: unknown) =>
    (await (await page.request.post(path, { data, headers: CSRF })).json()) as {
      today: string;
    };
  const plan = (await (await page.request.get("/api/plan")).json()) as { today: string };
  await post("/api/plan/meals", { main_id: meals.tacos, side_ids: [meals.rice], day: plan.today });
  await post("/api/plan/meals", { main_id: meals.chicken, scale: "2" });
  const oil = (await (
    await page.request.post("/api/items", {
      data: { name: "Olive oil", product_id: "0000000000013" },
      headers: CSRF,
    })
  ).json()) as { id: string };
  await page.request.patch(`/api/items/${oil.id}`, { data: { is_staple: true }, headers: CSRF });
  await post("/api/plan/extras", { item_id: oil.id, quantity: "1" });
  await page.request.put(`/api/plan/items/${oil.id}`, {
    data: { have_it: null, always: false },
    headers: CSRF,
  });
  const milk = (await (
    await page.request.post("/api/items", {
      data: { name: "Milk", product_id: "0000000000001" },
      headers: CSRF,
    })
  ).json()) as { id: string };
  await post("/api/plan/extras", { item_id: milk.id, quantity: "1" });
  await post("/api/plan/extras", { text: "Birthday candles", quantity: "1" });
}

// Playwright's WebKit screenshot code injects an inline <style>, which our CSP blocks and
// reports. Every other spec keeps the CSP guard on, so real violations are still caught.
test.use({ cspGuard: false });

const SCREENS = [
  { name: "plan", path: "/", heading: "This week" },
  { name: "meals", path: "/meals", heading: "Meals" },
  { name: "list", path: "/list", heading: "Shopping list" },
  { name: "more", path: "/more", heading: "More" },
  { name: "settings", path: "/settings", heading: "Settings" },
  { name: "about", path: "/about", heading: "About & privacy" },
];

for (const scheme of ["light", "dark"] as const) {
  test(`@screenshots ${scheme}`, async ({ page }, testInfo) => {
    test.skip(!process.env.SCREENSHOTS, "run with `just screenshots`");
    await page.emulateMedia({ colorScheme: scheme });
    const dir = `../.screenshots/${testInfo.project.name}`;
    await page.goto("/sign-in");
    await expect(page.getByLabel("Household password")).toBeVisible();
    await page.screenshot({ path: `${dir}/sign-in-${scheme}.png`, caret: "initial" });
    await page.getByRole("button", { name: "Use a code from another phone" }).click();
    await page.getByLabel("Code from another phone").fill("ABCD 2345");
    await page.screenshot({ path: `${dir}/sign-in-code-${scheme}.png`, caret: "initial" });
    // A scanned Add-a-phone code (synthetic): WebKit shows the iPhone version.
    await page.goto("/join#ABCD2345");
    await expect(page.getByText("ABCD 2345")).toBeVisible();
    await page.screenshot({ path: `${dir}/join-${scheme}.png`, fullPage: true, caret: "initial" });
    await page.goto("/install?from=more");
    await expect(
      page.getByRole("heading", { name: "Put Dinner Bell on your home screen" }),
    ).toBeVisible();
    await page.screenshot({
      path: `${dir}/install-${scheme}.png`,
      fullPage: true,
      caret: "initial",
    });
    await signIn(page);
    await page.goto("/who");
    await expect(page.getByRole("heading", { name: "Who’s using this phone?" })).toBeVisible();
    await page.screenshot({ path: `${dir}/who-${scheme}.png`, caret: "initial" });
    for (const screen of SCREENS) {
      await page.goto(screen.path);
      await expect(page.getByRole("heading", { name: screen.heading, exact: true })).toBeVisible();
      await page.screenshot({
        path: `${dir}/${screen.name}-${scheme}.png`,
        fullPage: true,
        // The default caret: "hide" injects an inline <style>, which our CSP rightly blocks.
        caret: "initial",
      });
    }

    const shot = async (name: string) => {
      await settle(page);
      await page.screenshot({
        path: `${dir}/${name}-${scheme}.png`,
        fullPage: true,
        caret: "initial",
      });
    };

    // First run, step 1, with stores found.
    await page.goto("/welcome");
    await page.getByLabel("Your ZIP code").fill("00001");
    await page.getByRole("button", { name: "Find stores" }).click();
    await expect(page.getByRole("list", { name: "Stores" })).toBeVisible();
    await shot("first-run-store");

    // The meal library, one meal, and the editor.
    const meals = await seedMeals(page);
    const tacos = meals.tacos;
    await page.goto("/meals");
    await expect(page.getByText("Sheet-pan chicken")).toBeVisible();
    await shot("meals-cards");
    await page.getByRole("button", { name: "On sale" }).click();
    await shot("meals-on-sale");
    await page.getByRole("button", { name: "On sale" }).click();
    await page.goto(`/meals/${tacos}`);
    await expect(page.getByRole("list", { name: "Items in this meal" })).toBeVisible();
    await shot("meal-detail");
    await page.goto(`/meals/${tacos}/edit`);
    await expect(page.getByRole("heading", { name: "Edit Tacos" })).toBeVisible();
    await shot("meal-edit");

    // Adding an item: Kroger's results at the store, then the amount picker's preview.
    await page.getByRole("button", { name: "Add an item" }).click();
    const sheet = page.getByRole("dialog", { name: "Add an item" });
    await sheet.getByLabel("What do you need?").fill("cheese");
    await expect(sheet.getByText("Sample Aged Gouda Cheese")).toBeVisible();
    await settle(page);
    await page.screenshot({ path: `${dir}/add-item-${scheme}.png`, caret: "initial" });
    // A new product is named first; one already in use (the cheddar) is that item again.
    await sheet.getByRole("button", { name: /Sample Aged Gouda Cheese/ }).click();
    await expect(sheet.getByLabel("What do you call it?")).toBeVisible();
    await settle(page);
    await page.screenshot({ path: `${dir}/add-item-name-${scheme}.png`, caret: "initial" });
    await sheet.getByRole("button", { name: "Choose another product" }).click();
    await sheet.getByRole("button", { name: /Sample Shredded Cheddar Cheese/ }).click();
    const picker = page.getByRole("dialog", { name: "How much?" });
    await picker.getByRole("button", { name: "1/2 bag" }).click();
    await expect(picker).toContainText("About half the 8 oz bag");
    await settle(page);
    await page.screenshot({ path: `${dir}/amount-picker-${scheme}.png`, caret: "initial" });

    // This week's plan, its sheets, and the list it builds.
    await seedPlan(page, meals);
    await page.goto("/");
    await expect(page.getByRole("region", { name: "Tonight" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Uses what you're buying" })).toBeVisible();
    await shot("plan-week");
    await page.getByRole("button", { name: "Add a meal" }).click();
    await expect(page.getByRole("dialog", { name: "Add a meal" })).toContainText("Tacos");
    await settle(page);
    await page.screenshot({ path: `${dir}/add-meal-${scheme}.png`, caret: "initial" });
    await page
      .getByRole("dialog", { name: "Add a meal" })
      .getByRole("button", { name: /Tacos/ })
      .click();
    await expect(page.getByRole("dialog", { name: "Add Tacos" })).toContainText("Usual sides");
    await page.screenshot({ path: `${dir}/add-meal-sides-${scheme}.png`, caret: "initial" });
    await page
      .getByRole("dialog", { name: "Add Tacos" })
      .getByRole("button", { name: "Close" })
      .click();
    await page.getByRole("button", { name: "Change Sheet-pan chicken" }).click();
    await expect(page.getByRole("dialog", { name: "Change Sheet-pan chicken" })).toBeVisible();
    await page.screenshot({ path: `${dir}/change-meal-${scheme}.png`, caret: "initial" });
    await page
      .getByRole("dialog", { name: "Change Sheet-pan chicken" })
      .getByRole("button", { name: "Close" })
      .click();
    await page.getByRole("link", { name: "List", exact: true }).click();
    await expect(page.getByRole("region", { name: "Check the pantry" })).toBeVisible();
    await shot("list-aisle");
    await page.emulateMedia({ media: "print", colorScheme: scheme });
    await shot("list-print");
    await page.emulateMedia({ media: "screen", colorScheme: scheme });
    await page.getByRole("button", { name: "By meal" }).click();
    await expect(page.getByRole("region", { name: "Sheet-pan chicken" })).toBeVisible();
    await shot("list-meal");
    await page.getByRole("button", { name: "By aisle" }).click();
    await page.getByRole("button", { name: /Ground beef/ }).click();
    await expect(page.getByRole("dialog", { name: "Ground beef" })).toBeVisible();
    await settle(page);
    await page.screenshot({ path: `${dir}/line-sheet-${scheme}.png`, caret: "initial" });
    await page
      .getByRole("dialog", { name: "Ground beef" })
      .getByRole("button", { name: "Swap product" })
      .click();
    await expect(page.getByRole("dialog", { name: "Ground beef" })).toContainText("per");
    await settle(page);
    await page.screenshot({ path: `${dir}/swap-${scheme}.png`, caret: "initial" });
    await page
      .getByRole("dialog", { name: "Ground beef" })
      .getByRole("button", { name: "Close" })
      .click();

    // Save the list, then shop it.
    await page.getByRole("button", { name: "Save list" }).click();
    await expect(page.getByRole("button", { name: "Start shopping" })).toBeVisible();
    await shot("list-saved");

    // Send to Kroger cart: not connected yet, then Connect Kroger (the demo sign-in page), Add a
    // phone, and the sheet before and after sending.
    await page.getByRole("button", { name: "Send to Kroger cart" }).click();
    const cart = page.getByRole("dialog", { name: "Send to Kroger cart" });
    await expect(cart).toContainText("Connect your Kroger account");
    await page.screenshot({ path: `${dir}/cart-not-connected-${scheme}.png`, caret: "initial" });
    await cart.getByRole("button", { name: "Go to Settings" }).click();
    await expect(page.getByRole("heading", { name: "Kroger account" })).toBeVisible();
    await shot("settings-kroger");
    await page.getByRole("button", { name: "Connect Kroger" }).click();
    await expect(page.getByRole("heading", { name: "Demo sign-in" })).toBeVisible();
    await page.getByRole("link", { name: "Allow", exact: true }).click();
    await expect(page.getByText("Kroger connected")).toBeVisible();
    await shot("settings-kroger-connected");
    await page.getByRole("button", { name: "Add a phone" }).click();
    await expect(page.getByTestId("join-code")).toBeVisible();
    await page.screenshot({ path: `${dir}/add-phone-${scheme}.png`, caret: "initial" });
    await page
      .getByRole("dialog", { name: "Add a phone" })
      .getByRole("button", { name: "Done" })
      .click();
    await page.getByRole("link", { name: "List", exact: true }).click();
    await page.getByRole("button", { name: "Send to Kroger cart" }).click();
    await expect(cart.getByRole("button", { name: /^Send \d+ items$/ })).toBeVisible();
    await settle(page);
    await page.screenshot({ path: `${dir}/cart-${scheme}.png`, caret: "initial" });
    await cart.getByRole("button", { name: /^Send \d+ items$/ }).click();
    await expect(cart.getByText(/^Added \d+ items to your Kroger cart\.$/)).toBeVisible();
    await settle(page);
    await page.screenshot({ path: `${dir}/cart-sent-${scheme}.png`, caret: "initial" });
    await cart.getByRole("button", { name: "Close" }).click();
    await page.getByRole("button", { name: "Start shopping" }).click();
    await expect(page.getByRole("region", { name: "Get ready for the store" })).toBeVisible();
    await shot("shopping");
    await page.getByRole("checkbox", { name: "Check off Tortillas" }).click();
    await page.getByRole("checkbox", { name: "Check off Salsa" }).click();
    await expect(page.getByText("Done (2)")).toBeVisible();
    await page.getByText("Done (2)").click();
    await shot("shopping-done");
    await page.getByRole("button", { name: /^Ground beef/ }).click();
    await expect(page.getByRole("dialog", { name: "Ground beef" })).toBeVisible();
    await settle(page);
    await page.screenshot({ path: `${dir}/shopping-item-${scheme}.png`, caret: "initial" });
    await page
      .getByRole("dialog", { name: "Ground beef" })
      .getByRole("button", { name: "Close" })
      .click();
    await page.getByRole("button", { name: "Finish trip" }).click();
    const finish = page.getByRole("dialog", { name: "Finish trip" });
    await finish.getByLabel("What did you pay? (optional)").fill("41.20");
    await page.screenshot({ path: `${dir}/finish-${scheme}.png`, caret: "initial" });
    await finish.getByRole("button", { name: "Finish trip" }).click();
    await expect(page.getByRole("heading", { name: "Trips" })).toBeVisible();
    await shot("trips");
    await page.getByRole("region", { name: "Finished trips" }).getByRole("link").first().click();
    await expect(page.getByRole("button", { name: "Shop this again" })).toBeVisible();
    await shot("trip-detail");

    // The store's walking order, from Settings.
    await page.getByRole("link", { name: "More", exact: true }).click();
    await page.getByRole("link", { name: "Settings" }).click();
    await page.getByRole("link", { name: "Store walking order" }).click();
    await expect(page.getByRole("list", { name: "Sections" })).toBeVisible();
    await shot("walking-order");
  });
}
