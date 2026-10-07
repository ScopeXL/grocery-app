/**
 * Item names (docs/UX.md §4.9 to §4.11): a store product gets the household's own name before
 * it's saved, a product already in use is that item again (never a twin), and an item can be
 * renamed later, with Undo. Synthetic data only.
 */
import { expect, signIn, test } from "./fixtures";
import { api, seedTacoNight } from "./seed";

test("a store product is named before it's saved, then reused", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "List", exact: true }).click();
  await page.getByRole("button", { name: "Add something else" }).click();
  const sheet = page.getByRole("dialog", { name: "Add something else" });
  await sheet.getByLabel("What do you need?").fill("mil");
  await sheet.getByRole("button", { name: /Sample Whole Milk/ }).click();
  await expect(sheet.getByLabel("What do you call it?")).toHaveValue("Milk");
  await sheet.getByRole("button", { name: "Add to list" }).click();
  await expect(page.getByText("Milk added")).toBeVisible();
  const extras = page.getByRole("region", { name: "Extras" });
  await expect(extras.getByRole("button", { name: /^Milk/ })).toBeVisible();

  // The same product again is the same item: still one Milk, and no "Same product" warning.
  await page.getByRole("button", { name: "Add something else" }).click();
  await sheet.getByLabel("What do you need?").fill("whole milk");
  const again = sheet.getByRole("button", { name: /Sample Whole Milk/ });
  await expect(again).toContainText("In your items as Milk");
  await again.click();
  await expect(sheet).toBeHidden();
  await expect(extras.getByRole("button", { name: /^Milk/ })).toHaveCount(1);
  await expect(extras.getByRole("button", { name: /^Milk/ })).toContainText("2");
  await expect(page.getByText(/Same product as/)).toHaveCount(0);
});

test("an item renamed from the list reads the new name, and Undo puts the old one back", async ({
  page,
}) => {
  await signIn(page);
  const seeded = await seedTacoNight(page);
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.tacos });
  await page.getByRole("link", { name: "List", exact: true }).click();
  await page.getByRole("button", { name: /^Shredded cheddar/ }).click();
  const sheet = page.getByRole("dialog", { name: "Shredded cheddar" });
  await sheet.getByRole("button", { name: "Rename Shredded cheddar" }).click();
  const field = sheet.getByLabel("What do you call it?");
  await expect(field).toBeFocused();
  await field.fill("Shredded cheese");
  await sheet.getByRole("button", { name: "Save name" }).click();

  const renamed = page.getByRole("dialog", { name: "Shredded cheese" });
  await expect(renamed.getByText("Renamed to Shredded cheese")).toBeVisible();
  await expect(renamed.getByRole("button", { name: "Rename Shredded cheese" })).toBeFocused();
  await renamed.getByRole("button", { name: "Undo" }).click();
  const back = page.getByRole("dialog", { name: "Shredded cheddar" });
  await expect(back).toBeVisible();
  await back.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("button", { name: /^Shredded cheddar/ })).toBeVisible();
});

test("an item renamed from a meal's amount picker shows in the meal", async ({ page }) => {
  await signIn(page);
  await seedTacoNight(page);
  await page.getByRole("link", { name: "Meals", exact: true }).click();
  await page.getByRole("link", { name: /Tacos/ }).first().click();
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByRole("button", { name: "Change Shredded cheddar" }).click();
  const picker = page.getByRole("dialog", { name: "How much?" });
  await picker.getByRole("button", { name: "Rename Shredded cheddar" }).click();
  await picker.getByLabel("What do you call it?").fill("Shredded cheese");
  await picker.getByRole("button", { name: "Save name" }).click();
  await expect(picker.getByRole("button", { name: "Rename Shredded cheese" })).toBeVisible();
  await picker.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("button", { name: "Change Shredded cheese" })).toBeVisible();
});
