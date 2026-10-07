/**
 * M5 acceptance (docs/PLAN.md §12): Connect Kroger through the demo sign-in page (sample mode's
 * stand-in for Kroger's), then send a saved list to the sample Kroger cart. Each item is added
 * once; sending again needs a second "yes"; an item Kroger refused goes again on its own.
 * Synthetic data only.
 */
import type { Page } from "@playwright/test";

import { expect, openSettings, signIn, test } from "./fixtures";
import { api, PRODUCTS, seedTacoNight } from "./seed";

interface CartItem {
  upc: string;
  quantity: number;
  modality: string;
}

async function fakeCart(page: Page): Promise<CartItem[]> {
  return (await (await page.request.get("/api/_test/fake-cart")).json()) as CartItem[];
}

async function connectKroger(page: Page): Promise<void> {
  await openSettings(page);
  await page.getByRole("button", { name: "Connect Kroger" }).click();
  await expect(page.getByRole("heading", { name: "Demo sign-in" })).toBeVisible();
  await page.getByRole("link", { name: "Allow", exact: true }).click();
  await expect(page.getByText("Kroger connected")).toBeVisible();
  await expect(page.getByText("By Sample Parent", { exact: true })).toBeVisible();
}

/** Tacos and Chili, saved as a list (through the API), then the List tab. */
async function savedList(page: Page): Promise<void> {
  const seeded = await seedTacoNight(page);
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.tacos });
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.chili });
  await api(page, "POST", "/api/trips");
  await page.getByRole("link", { name: "List", exact: true }).click();
  await expect(page.getByRole("button", { name: "Start shopping" })).toBeVisible();
}

test("Connect Kroger through the sign-in page, and disconnect", async ({ page }) => {
  await signIn(page);
  await connectKroger(page);
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByText("Send lists for")).toBeVisible();

  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.getByText("Kroger disconnected")).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect Kroger" })).toBeVisible();
});

test("saying no on the sign-in page leaves Kroger unconnected", async ({ page }) => {
  await signIn(page);
  await openSettings(page);
  await page.getByRole("button", { name: "Connect Kroger" }).click();
  await page.getByRole("link", { name: "Don't allow" }).click();
  await expect(page.getByText("Kroger wasn't connected")).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect Kroger" })).toBeVisible();
});

test("a saved list goes to the Kroger cart once", async ({ page }) => {
  await signIn(page);
  await connectKroger(page);
  await savedList(page);

  await page.getByRole("button", { name: "Send to Kroger cart" }).click();
  const sheet = page.getByRole("dialog", { name: "Send to Kroger cart" });
  await expect(sheet.getByRole("group", { name: "Pickup or delivery?" })).toBeVisible();
  await expect(sheet.getByText("Sold by the pound. Add it in the Kroger app.")).toBeVisible();
  await sheet.getByRole("button", { name: "Delivery" }).click();
  await sheet.getByRole("button", { name: "Send 4 items" }).click();
  await expect(sheet.getByText("Added 4 items to your Kroger cart.")).toBeVisible();
  await expect(sheet.getByRole("region", { name: "In your Kroger cart" })).toContainText(
    "Sent by Sample Parent",
  );
  const sent = await fakeCart(page);
  expect(sent).toHaveLength(4);
  expect(sent.every((item) => item.modality === "DELIVERY")).toBe(true);
  expect(sent.find((item) => item.upc === PRODUCTS.beef)?.quantity).toBe(2);

  // Opening it again says so, and sending again needs a second yes.
  await sheet.getByRole("button", { name: "Close" }).click();
  await page.getByRole("button", { name: "Send to Kroger cart" }).click();
  await expect(sheet.getByText("Everything here is already in your Kroger cart.")).toBeVisible();
  await sheet.getByRole("button", { name: "Send again anyway" }).click();
  const confirm = page.getByRole("dialog", { name: "Send again?" });
  await confirm.getByRole("button", { name: "Keep my cart as it is" }).click();
  await expect(sheet.getByText("Everything here is already in your Kroger cart.")).toBeVisible();
  expect(await fakeCart(page)).toHaveLength(4);

  await sheet.getByRole("button", { name: "Send again anyway" }).click();
  await confirm.getByRole("button", { name: "Send 4 items again" }).click();
  await expect(sheet.getByText("Added 4 items to your Kroger cart.")).toBeVisible();
  expect(await fakeCart(page)).toHaveLength(8);
});

test("an item Kroger refuses can be sent again on its own", async ({ page }) => {
  await signIn(page);
  await connectKroger(page);
  await savedList(page);
  await page.request.put("/api/_test/fake-cart", {
    data: { reject_upcs: [PRODUCTS.shells] },
    headers: { "X-Dinner-Bell": "1" },
  });

  await page.getByRole("button", { name: "Send to Kroger cart" }).click();
  const sheet = page.getByRole("dialog", { name: "Send to Kroger cart" });
  await sheet.getByRole("button", { name: "Send 4 items" }).click();
  await expect(
    sheet.getByText("Added 3 items to your Kroger cart. 1 item didn't go; see below."),
  ).toBeVisible();
  const trouble = sheet.getByRole("region", { name: "Didn’t go" });
  await expect(trouble).toContainText("Taco shells");
  await expect(trouble).toContainText("Kroger didn't take this item.");

  await page.request.put("/api/_test/fake-cart", {
    data: {},
    headers: { "X-Dinner-Bell": "1" },
  });
  await sheet.getByRole("button", { name: "Send these again" }).click();
  await expect(sheet.getByText("Added 1 item to your Kroger cart.")).toBeVisible();
  await expect(sheet.getByText("Everything here is already in your Kroger cart.")).toBeHidden();
  const upcs = (await fakeCart(page)).map((item) => item.upc);
  expect(upcs.filter((upc) => upc === PRODUCTS.shells)).toHaveLength(1);
  expect(upcs).toHaveLength(4);
});

test("without a Kroger account, the sheet says where to connect it", async ({ page }) => {
  await signIn(page);
  await savedList(page);
  await page.getByRole("button", { name: "Send to Kroger cart" }).click();
  const sheet = page.getByRole("dialog", { name: "Send to Kroger cart" });
  await expect(sheet.getByText(/Connect your Kroger account in Settings first/)).toBeVisible();
  await sheet.getByRole("button", { name: "Go to Settings" }).click();
  await expect(page.getByRole("button", { name: "Connect Kroger" })).toBeVisible();
});
