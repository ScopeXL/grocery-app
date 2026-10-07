/**
 * Motion (ADR 0027, docs/UX.md §7.6): sheets slide up and away without losing focus or taps,
 * and with Reduce Motion everything still works, instantly. Synthetic data only.
 */
import type { Page } from "@playwright/test";

import { expect, openSettings, settled, signIn, test } from "./fixtures";
import { api, seedTacoNight } from "./seed";

/** Tacos planned, so the plan has one "Add a meal" button. */
async function planWithTacos(page: Page): Promise<void> {
  const seeded = await seedTacoNight(page);
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.tacos });
  await expect(page.getByRole("list", { name: "This week's meals" })).toContainText("Tacos");
}

test("a sheet opens with focus on itself, and gives it back when it slides away", async ({
  page,
}) => {
  await signIn(page);
  await planWithTacos(page);
  const opener = page.getByRole("button", { name: "Add a meal" });
  await opener.focus();
  await page.keyboard.press("Enter");
  const sheet = page.getByRole("dialog", { name: "Add a meal" });
  await expect(sheet).toBeFocused(); // the sheet, so its Close button doesn't look pressed
  await page.keyboard.press("Escape");
  await expect(page.locator("dialog[open]")).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("Send again? takes over from the cart sheet and hands back, keeping focus", async ({
  page,
}) => {
  await signIn(page);
  await openSettings(page);
  await page.getByRole("button", { name: "Connect Kroger" }).click();
  await page.getByRole("link", { name: "Allow", exact: true }).click();
  await expect(page.getByText("Kroger connected")).toBeVisible();
  const seeded = await seedTacoNight(page);
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.tacos });
  await api(page, "POST", "/api/trips");
  await page.getByRole("link", { name: "List", exact: true }).click();
  await page.getByRole("button", { name: "Send to Kroger cart" }).click();
  const sheet = page.getByRole("dialog", { name: "Send to Kroger cart" });
  await sheet.getByRole("button", { name: /^Send \d+ items$/ }).click();
  await expect(sheet.getByText(/^Added \d+ items to your Kroger cart\.$/)).toBeVisible();

  await sheet.getByRole("button", { name: "Send again anyway" }).click();
  const confirm = page.getByRole("dialog", { name: "Send again?" });
  await expect(confirm).toBeVisible();
  await settled(page); // the cart sheet has finished sliding away and closed
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(confirm).toBeFocused();

  await confirm.getByRole("button", { name: "Keep my cart as it is" }).click();
  await expect(sheet).toBeVisible();
  await settled(page);
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(sheet).toBeFocused();
});

test.describe("with Reduce Motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("sheets open and close at once", async ({ page }) => {
    await signIn(page);
    await planWithTacos(page);
    await page.getByRole("button", { name: "Add a meal" }).click();
    const sheet = page.getByRole("dialog", { name: "Add a meal" });
    await expect(sheet).toBeVisible();
    const seconds = await sheet.evaluate((dialog) =>
      parseFloat(getComputedStyle(dialog).animationDuration),
    );
    expect(seconds).toBeLessThan(0.001);
    await sheet.getByRole("button", { name: "Close" }).click();
    await expect(page.locator("dialog[open]")).toHaveCount(0, { timeout: 500 });
    await page.getByRole("button", { name: "Change Tacos" }).click();
    await expect(page.getByRole("dialog", { name: "Change Tacos" })).toBeVisible();
  });
});
