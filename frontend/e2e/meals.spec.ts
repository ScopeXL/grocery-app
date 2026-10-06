/**
 * M1 acceptance (docs/PLAN.md §12): choose a store (fake Kroger), create a Main with 4 items,
 * one by weight and one by count, add a photo, then archive it and undo. Synthetic data only.
 */
import type { Page } from "@playwright/test";

import { expect, signIn, test } from "./fixtures";

// A 1×1 PNG: enough for the phone to shrink and the server to re-encode as WebP.
const PHOTO = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

async function addItem(page: Page, search: string, product: string): Promise<void> {
  await page.getByRole("button", { name: "Add an item" }).click();
  const sheet = page.getByRole("dialog", { name: "Add an item" });
  await sheet.getByLabel("What do you need?").fill(search);
  await sheet.getByRole("button", { name: new RegExp(product) }).click();
  await expect(page.getByRole("dialog", { name: "How much?" })).toBeVisible();
}

async function done(page: Page): Promise<void> {
  const picker = page.getByRole("dialog", { name: "How much?" });
  await expect(picker.getByRole("button", { name: "Done" })).toBeEnabled();
  await picker.getByRole("button", { name: "Done" }).click();
  await expect(picker).toBeHidden();
}

test("first run: choose a store, add Tacos with four items and a photo, archive and undo", async ({
  page,
}) => {
  await signIn(page, "Sample Parent", { withStore: false });

  // Step 1: the store, by ZIP. Fuel centers never show.
  await page.getByLabel("Your ZIP code").fill("00001");
  await page.getByRole("button", { name: "Find stores" }).click();
  const stores = page.getByRole("list", { name: "Stores" });
  await expect(stores.getByRole("button")).toHaveCount(2);
  await expect(stores).not.toContainText("Fuel");
  await stores.getByRole("button", { name: /Sample Market Downtown/ }).click();

  // Step 2: the first dinner, guided.
  await page.getByRole("button", { name: "Add your first dinner" }).click();
  await expect(page.getByRole("heading", { name: "New meal" })).toBeVisible();
  await page.getByLabel("Meal name").fill("Tacos");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: /^Main/ }).click();
  await expect(page.getByRole("button", { name: "Dinner" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: "Next" }).click();

  // Part of a package, with a live preview of the share and its cost.
  await addItem(page, "cheddar", "Sample Shredded Cheddar Cheese");
  const picker = page.getByRole("dialog", { name: "How much?" });
  await picker.getByRole("button", { name: "1/2 bag" }).click();
  await expect(picker).toContainText("About half the 8 oz bag");
  await expect(picker).toContainText("about $1.25");
  await done(page);

  // By weight.
  await addItem(page, "ground beef", "Sample Ground Beef");
  await picker.getByLabel("Unit").selectOption("lb");
  await done(page);

  // By count: typed, then stepped (counts step by halves).
  await addItem(page, "tortillas", "Sample Flour Tortillas");
  const count = picker.getByRole("textbox", { name: "How many" });
  await count.fill("3");
  await picker.getByRole("button", { name: "More" }).click();
  await picker.getByRole("button", { name: "More" }).click();
  await expect(count).toHaveValue("4");
  await expect(picker).toContainText("about $0.92"); // 4 of 10 at $2.29
  await done(page);

  await addItem(page, "salsa", "Sample Chunky Salsa");
  await picker.getByRole("button", { name: "1/2 package" }).click();
  await done(page);

  const lines = page.locator("ul").filter({ hasText: "Cheddar" });
  for (const amount of ["1/2 bag", "1 lb", "4", "1/2 package"]) {
    await expect(lines).toContainText(amount);
  }
  await page.getByRole("button", { name: "Next" }).click();

  // Step 3 of the meal: a photo, then save.
  await page.getByLabel("Choose a photo").setInputFiles({
    name: "tacos.png",
    mimeType: "image/png",
    buffer: PHOTO,
  });
  await expect(page.getByRole("button", { name: "Change photo" })).toBeVisible();
  await page.getByRole("button", { name: "Save meal" }).click();
  await expect(page.getByText("Meal saved")).toBeVisible();
  await expect(page.getByRole("heading", { name: "You're set." })).toBeVisible();

  // The library card shows the photo and an estimated cost.
  await page.getByRole("button", { name: "Go to Meals" }).click();
  const card = page.getByRole("listitem").filter({ hasText: "Tacos" });
  await expect(card).toContainText(/about \$\d+/);
  await expect(card.locator('img[src^="/api/photos/"]')).toBeVisible();

  // Archive, then Undo from the toast: nothing is lost.
  await card.getByRole("link").click();
  await expect(page.getByRole("heading", { name: "Tacos" })).toBeVisible();
  const items = page.getByRole("list", { name: "Items in this meal" });
  await expect(items.getByRole("listitem")).toHaveCount(4);
  await expect(items).not.toContainText("Check amount");
  await page.getByRole("button", { name: "Archive" }).click();
  await expect(page.getByText("Tacos archived")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Tacos" })).toHaveCount(0);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "Tacos" })).toBeVisible();

  // The chosen store shows in Settings (reached in the app; a reload mid-request trips WebKit).
  await page.getByRole("link", { name: "More", exact: true }).click();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await expect(page.getByText("Sample Market Downtown")).toBeVisible();
  await expect(page.getByText("100 Sample Street")).toBeVisible();
});

test("a draft survives leaving the editor", async ({ page }) => {
  await signIn(page);
  await page.goto("/meals/new?role=side");
  await page.getByLabel("Meal name").fill("Lime rice");
  await page.getByRole("button", { name: "Next" }).click();
  await page.goto("/meals");
  await expect(page.getByText("Your meals live here.")).toBeVisible(); // loaded before reloading
  await page.goto("/meals/new?role=side");
  await expect(page.getByText("Picking up where you left off.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Is it a main or a side?" })).toBeVisible();
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page.getByLabel("Meal name")).toHaveValue("Lime rice");
});

test("searching shows quiet states, never an error wall", async ({ page }) => {
  await signIn(page);
  await page.goto("/meals/new?role=main");
  await page.getByLabel("Meal name").fill("Anything");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: /^Main/ }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Add an item" }).click();
  const sheet = page.getByRole("dialog", { name: "Add an item" });
  await sheet.getByLabel("What do you need?").fill("xyzzy");
  await expect(sheet).toContainText("Nothing at your store matches “xyzzy”.");
  await expect(sheet.getByRole("button", { name: "Add “Xyzzy” as plain text" })).toBeVisible();
  await sheet.getByLabel("What do you need?").fill("dailylimit");
  await expect(sheet).toContainText("Store search is paused until about");
  await expect(sheet).toContainText("your list still works");
});
