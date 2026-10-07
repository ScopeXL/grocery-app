/**
 * M2 acceptance (docs/PLAN.md §12): plan Tacos ×2 and Chili, which share ground beef. The list
 * merges and rounds, and the total equals a hand-computed fixture. A second phone sees a plan
 * change within 2 seconds. Synthetic data only; the fake store's sales follow the clock.
 */
import type { Page } from "@playwright/test";

import { expect, signIn, test } from "./fixtures";
import { api, seedTacoNight } from "./seed";

async function addMeal(page: Page, name: string, sides: string[] = []): Promise<void> {
  await page.getByRole("button", { name: "Add a meal" }).click();
  await page.getByRole("dialog", { name: "Add a meal" }).getByRole("button", { name }).click();
  const sheet = page.getByRole("dialog", { name: `Add ${name}` });
  for (const side of sides) await sheet.getByRole("button", { name: side, exact: true }).click();
  await sheet.getByRole("button", { name: sides.length ? "Add to plan" : "Skip sides" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByText(`${name} added`)).toBeVisible();
}

test("a meal's day is a Sunday-to-Saturday pill, tapped again to clear", async ({ page }) => {
  await signIn(page);
  await seedTacoNight(page);
  await page.getByRole("button", { name: "Add a meal" }).click();
  await page
    .getByRole("dialog", { name: "Add a meal" })
    .getByRole("button", { name: "Tacos" })
    .click();
  const sheet = page.getByRole("dialog", { name: "Add Tacos" });
  const days = sheet.getByRole("group", { name: "Day" });
  await expect(days.getByRole("button")).toHaveCount(7);
  await expect(days.getByRole("button").first()).toContainText("Sun");
  await expect(sheet.getByText("Any day", { exact: true })).toBeVisible();
  const today = days.getByRole("button", { name: /today/ });
  await today.click();
  await expect(today).toHaveAttribute("aria-pressed", "true");
  await expect(sheet.getByText("Today", { exact: true })).toBeVisible();
  await today.click();
  await expect(today).toHaveAttribute("aria-pressed", "false");
  await expect(sheet.getByText("Any day", { exact: true })).toBeVisible();
  await today.click();
  await sheet.getByRole("button", { name: "Skip sides" }).click();
  await expect(page.getByRole("region", { name: "Tonight" })).toContainText("Tacos");

  // In Change, tapping the chosen day again clears it, and Tacos leaves Tonight.
  await page.getByRole("button", { name: "Change Tacos" }).click();
  const change = page.getByRole("dialog", { name: "Change Tacos" });
  await change.getByRole("group", { name: "Day" }).getByRole("button", { name: /today/ }).click();
  await expect(change.getByText("Any day", { exact: true })).toBeVisible();
  await change.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("region", { name: "Tonight" })).toHaveCount(0);
  await expect(page.getByRole("list", { name: "This week's meals" })).toContainText("Tacos");
});

test("what a meal is for is chosen when planning, and remembered", async ({ page }) => {
  await signIn(page);
  await seedTacoNight(page);
  await page.getByRole("button", { name: "Add a meal" }).click();
  const pick = page.getByRole("dialog", { name: "Add a meal" });
  // Every main is listed: no occasion filter.
  await expect(pick.getByRole("button", { name: /^Chili/ })).toBeVisible();
  await pick.getByRole("button", { name: /^Tacos/ }).click();
  const sheet = page.getByRole("dialog", { name: "Add Tacos" });
  const eatFor = sheet.getByRole("group", { name: "Eat it for" });
  await expect(eatFor.getByRole("button", { name: "Dinner" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await eatFor.getByRole("button", { name: "Lunch" }).click();
  await sheet.getByRole("button", { name: "Skip sides" }).click();
  await expect(page.getByRole("list", { name: "This week's meals" })).toContainText("Lunch");

  // Next time, Tacos starts as lunch.
  await page.getByRole("button", { name: "Add a meal" }).click();
  await page
    .getByRole("dialog", { name: "Add a meal" })
    .getByRole("button", { name: /^Tacos/ })
    .click();
  await expect(
    page
      .getByRole("dialog", { name: "Add Tacos" })
      .getByRole("group", { name: "Eat it for" })
      .getByRole("button", { name: "Lunch" }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("plan Tacos twice and Chili: the list merges, rounds and adds up", async ({ page }) => {
  await signIn(page);
  await seedTacoNight(page);

  await addMeal(page, "Tacos", ["Rice"]);
  await page.getByRole("button", { name: "Change Tacos" }).click();
  const change = page.getByRole("dialog", { name: "Change Tacos" });
  await change.getByRole("button", { name: "×2" }).click();
  await expect(change.getByRole("button", { name: "×2" })).toHaveAttribute("aria-pressed", "true");
  await change.getByRole("button", { name: "Close" }).click();
  await addMeal(page, "Chili");

  const meals = page.getByRole("list", { name: "This week's meals" });
  await expect(meals).toContainText("with Rice");
  await expect(meals).toContainText("×2");

  // By hand: beef 2 x 1 lb + 1/2 = 2 1/2 -> 3 packages at the $4.99 sale price = $14.97;
  // shells 12 of 12 -> 1 at $2.29; cheddar 2 halves -> 1 bag at $2.50; beans 2 cans at $1.09
  // = $2.18; onion 8 oz -> 1/2 lb at $1.49 = $0.75; rice 2 quarters -> 1 bag at $2.19.
  // Total $24.88 (about $25); the beef sale saves 3 x $0.50.
  await expect(page.getByTestId("total")).toHaveText("About $25");
  await expect(page.getByText("$1.50 off on sale")).toBeVisible();

  await page.getByRole("link", { name: "List", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Shopping list" })).toBeVisible();
  const beef = page.getByRole("button", { name: /Ground beef/ });
  await expect(beef).toContainText("3 packages, 1 lb each");
  await expect(beef).toContainText("about $15");
  await expect(beef).toContainText("Sale");
  await expect(beef).toContainText("for Tacos and Chili");
  await expect(page.getByRole("button", { name: /Taco shells/ })).toContainText("1 package, 12 ct");
  await expect(page.getByRole("button", { name: /Black beans/ })).toContainText(
    "2 cans, 15 oz each",
  );
  await expect(page.getByRole("button", { name: /Yellow onion/ })).toContainText("1/2 lb");
  await expect(page.getByTestId("total")).toHaveText("About $25");

  // The same lines, by meal: shared beef sits under the first meal that uses it.
  await page.getByRole("button", { name: "By meal" }).click();
  await expect(page.getByRole("region", { name: "Tacos" })).toContainText("Ground beef");
  await expect(page.getByRole("region", { name: "Chili" })).not.toContainText("Ground beef");
});

test("the pantry check, usuals and a changed quantity move the total", async ({ page }) => {
  await signIn(page);
  const seeded = await seedTacoNight(page);
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.tacos, side_ids: [seeded.salad] });
  // Milk was added once before, so it's a usual.
  const added = await api(page, "POST", "/api/plan/extras", {
    item_id: seeded.milk,
    quantity: "1",
  });
  await api(page, "DELETE", `/api/plan/extras/${String(added.changed)}`);

  await page.getByRole("link", { name: "List", exact: true }).click();
  const pantry = page.getByRole("region", { name: "Check the pantry" });
  await expect(pantry).toContainText("Check the pantry: 1 staple");
  // Beef $4.99 (sale) + shells $2.29 + cheddar $2.50 + a bottle of oil $8.99 = $18.77.
  const total = page.getByTestId("total");
  await expect(total).toHaveText("About $19");
  await pantry.getByRole("button", { name: "Have Cooking oil" }).click();
  await expect(pantry).toBeHidden();
  await expect(page.getByRole("button", { name: /Cooking oil/ })).toContainText("Have it");
  await expect(total).toHaveText("About $10"); // $9.78

  await page.getByRole("group", { name: "Usuals" }).getByRole("button", { name: "Milk" }).click();
  await expect(page.getByText("Milk added")).toBeVisible();
  const extras = page.getByRole("region", { name: "Extras" });
  await expect(extras.getByRole("button", { name: /Milk/ })).toContainText(
    "Added by Sample Parent",
  );
  await expect(total).toHaveText("About $13"); // + $2.99 milk on sale = $12.77

  // One more box of shells than the plan needs; the stepper keeps the difference.
  await page.getByRole("button", { name: /Taco shells/ }).click();
  const sheet = page.getByRole("dialog", { name: "Taco shells" });
  await sheet.getByRole("button", { name: "One more" }).click();
  await expect(sheet).toContainText("2 packages");
  await expect(sheet).toContainText("The list works out 1.");
  await sheet.getByRole("button", { name: "Close" }).click();
  await expect(total).toHaveText("About $15"); // + $2.29 = $15.06
});

test("a second phone sees a plan change within 2 seconds", async ({ page, browser }) => {
  await signIn(page, "Sample Parent");
  await seedTacoNight(page);
  const other = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const otherPage = await other.newPage();
  await signIn(otherPage, "Sample Kid");
  // In-app links, not a reload (CLAUDE.md gotchas: WebKit and reloads mid-request).
  await otherPage.getByRole("link", { name: "More", exact: true }).click();
  await otherPage.getByRole("link", { name: "Settings" }).click();
  await expect(otherPage.getByTestId("live-status")).toHaveText("Live updates: connected");
  await otherPage.getByRole("link", { name: "Plan", exact: true }).click();
  await expect(otherPage.getByText("No meals planned yet.")).toBeVisible();

  await addMeal(page, "Chili");
  await expect(otherPage.getByRole("link", { name: "Chili" })).toBeVisible({ timeout: 2000 });
  await other.close();
});
