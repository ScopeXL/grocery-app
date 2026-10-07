/**
 * M4 acceptance (docs/PLAN.md §12): a suggested meal says what it would add, and adding it moves
 * the total by that much (±$1, at display rounding); Meals can be filtered to what's on sale.
 * Synthetic data only; the fake store's sales follow the clock.
 */
import { expect, signIn, test } from "./fixtures";
import { api, dish, item, line, PRODUCTS } from "./seed";

async function tacoNight(page: import("@playwright/test").Page) {
  const beef = await item(page, "Ground beef", PRODUCTS.beef);
  const cheddar = await item(page, "Shredded cheddar", PRODUCTS.cheddar);
  const shells = await item(page, "Taco shells", PRODUCTS.shells);
  const romaine = await item(page, "Romaine", "0000000000009");
  const salsa = await item(page, "Salsa", PRODUCTS.salsa);
  const rice = await item(page, "White rice", PRODUCTS.rice);
  const tacos = await dish(page, {
    name: "Tacos",
    role: "main",
    lines: [
      line(beef, "packages", "1/2"),
      line(cheddar, "packages", "1/2"),
      line(romaine, "count", "1"),
      line(shells, "count", "6"),
    ],
  });
  await dish(page, {
    name: "Taco salad",
    role: "main",
    lines: [
      line(beef, "packages", "1/2"),
      line(cheddar, "packages", "1/2"),
      line(romaine, "count", "1"),
      line(salsa, "packages", "1/2"),
    ],
  });
  await dish(page, { name: "Rice bowl", role: "main", lines: [line(rice, "packages", "1/2")] });
  return { tacos };
}

function dollars(text: string | null): number {
  const match = /\$(\d[\d,]*)/.exec(text ?? "");
  return match ? Number((match[1] ?? "0").replace(/,/g, "")) : Number.NaN;
}

test("adding a suggested meal moves the total by about what it says", async ({ page }) => {
  await signIn(page);
  const { tacos } = await tacoNight(page);
  await api(page, "POST", "/api/plan/meals", { main_id: tacos });
  await page.getByRole("link", { name: "Meals", exact: true }).click();
  await page.getByRole("link", { name: "Plan", exact: true }).click();

  const strip = page.getByRole("region", { name: "Uses what you're buying" });
  await expect(strip).toContainText("Taco salad uses your leftover");
  const reason = (await strip.getByRole("listitem").first().textContent()) ?? "";
  const shown = /Adds about \$(\d+)/.exec(reason);
  const adds = shown ? Number(shown[1]) : 0; // "Nothing extra to buy." is $0
  const before = dollars(await page.getByTestId("total").textContent());

  await strip.getByRole("button", { name: "Add Taco salad" }).click();
  await expect(page.getByText("Taco salad added")).toBeVisible();
  await expect
    .poll(async () => dollars(await page.getByTestId("total").textContent()) - before)
    .toBeGreaterThanOrEqual(adds - 1);
  const after = dollars(await page.getByTestId("total").textContent());
  expect(Math.abs(after - before - adds)).toBeLessThanOrEqual(1);
  await expect(page.getByRole("list", { name: "This week's meals" })).toContainText("Taco salad");
});

test("Meals can show only what's on sale", async ({ page }) => {
  await signIn(page);
  await tacoNight(page);
  await page.getByRole("link", { name: "Meals", exact: true }).click();
  await expect(page.getByText("Rice bowl")).toBeVisible();
  await page.getByRole("button", { name: "On sale" }).click();
  await expect(page.getByText("Rice bowl")).toBeHidden();
  await expect(page.getByRole("link", { name: /Tacos/ })).toContainText("Sale");
});
