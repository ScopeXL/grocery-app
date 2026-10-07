/**
 * Synthetic meals and items, made through the API with the page's own session. The fake
 * store's products and prices are in backend/src/dinnerbell/kroger/fixtures/products.json.
 */
import type { Page } from "@playwright/test";

const CSRF = { "X-Dinner-Bell": "1" };

export const PRODUCTS = {
  milk: "0000000000001",
  cheddar: "0000000000002",
  beef: "0000000000003",
  onion: "0000000000004",
  tortillas: "0000000000005",
  shells: "0000000000006",
  rice: "0000000000007",
  salsa: "0000000000008",
  beans: "0000000000010",
  oil: "0000000000013",
  thighs: "0000000000014",
} as const;

export function line(item_id: string, kind: string, value: string, unit: string | null = null) {
  return { item_id, amount: { kind, value, unit } };
}

export async function item(page: Page, name: string, productId?: string): Promise<string> {
  const response = await page.request.post("/api/items", {
    data: productId ? { name, product_id: productId } : { name },
    headers: CSRF,
  });
  return ((await response.json()) as { id: string }).id;
}

export async function dish(page: Page, body: Record<string, unknown>): Promise<string> {
  const response = await page.request.post("/api/dishes", {
    data: { favorite: false, ...body },
    headers: CSRF,
  });
  return ((await response.json()) as { id: string }).id;
}

export async function api(
  page: Page,
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  data?: unknown,
) {
  const response = await page.request.fetch(path, {
    method,
    headers: CSRF,
    ...(data === undefined ? {} : { data }),
  });
  return (await response.json()) as Record<string, unknown>;
}

/**
 * Tacos and Chili share ground beef; Rice and Side salad are sides; cooking oil is a staple.
 *
 * Tacos: 1 lb beef, 6 of the 12 shells, half the 8 oz bag of cheddar.
 * Chili: half a package of beef, 2 cans of beans, 8 oz of onion (sold by the pound).
 * Rice: a quarter of the 2 lb bag. Side salad: 1 tbsp of oil.
 */
export async function seedTacoNight(page: Page) {
  const beef = await item(page, "Ground beef", PRODUCTS.beef);
  const shells = await item(page, "Taco shells", PRODUCTS.shells);
  const cheddar = await item(page, "Shredded cheddar", PRODUCTS.cheddar);
  const beans = await item(page, "Black beans", PRODUCTS.beans);
  const onion = await item(page, "Yellow onion", PRODUCTS.onion);
  const rice = await item(page, "White rice", PRODUCTS.rice);
  const oil = await item(page, "Cooking oil", PRODUCTS.oil);
  const milk = await item(page, "Milk", PRODUCTS.milk);
  await api(page, "PATCH", `/api/items/${oil}`, { is_staple: true });
  const tacos = await dish(page, {
    name: "Tacos",
    role: "main",
    favorite: true,
    lines: [
      line(beef, "measure", "1", "lb"),
      line(shells, "count", "6"),
      line(cheddar, "packages", "1/2"),
    ],
  });
  const chili = await dish(page, {
    name: "Chili",
    role: "main",
    lines: [
      line(beef, "packages", "1/2"),
      line(beans, "packages", "2"),
      line(onion, "measure", "8", "oz"),
    ],
  });
  const riceSide = await dish(page, {
    name: "Rice",
    role: "side",
    lines: [line(rice, "packages", "1/4")],
  });
  const salad = await dish(page, {
    name: "Side salad",
    role: "side",
    lines: [line(oil, "measure", "1", "tbsp")],
  });
  return { tacos, chili, riceSide, salad, milk, oil, cheddar };
}
