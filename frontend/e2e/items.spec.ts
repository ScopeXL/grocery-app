/**
 * Item names (docs/UX.md §4.9): a store product gets the household's own name before it's
 * saved, and a product already in use is that item again, never a twin. Synthetic data only.
 */
import { expect, signIn, test } from "./fixtures";

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
