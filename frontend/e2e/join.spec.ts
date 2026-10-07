/**
 * M5 (docs/PLAN.md §10.2): add a phone without the household password. A signed-in phone shows a
 * one-time code; the new phone scans it (the QR code opens /join#<code>) or types it on the
 * sign-in screen. Synthetic data only.
 */
import type { Browser, Page } from "@playwright/test";

import { expect, openSettings, signIn, test } from "./fixtures";

async function makeCode(page: Page): Promise<string> {
  await openSettings(page);
  await page.getByRole("button", { name: "Add a phone" }).click();
  const sheet = page.getByRole("dialog", { name: "Add a phone" });
  await expect(
    sheet.getByRole("img", { name: "QR code that signs in another phone" }),
  ).toBeVisible();
  const shown = (await sheet.getByTestId("join-code").locator("[aria-hidden]").textContent()) ?? "";
  expect(shown).toMatch(/^[A-Z2-9]{4} [A-Z2-9]{4}$/);
  return shown.replace(" ", "");
}

async function newPhone(browser: Browser): Promise<Page> {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  return context.newPage();
}

test("a scanned code signs in a new phone", async ({ page, browser }) => {
  await signIn(page);
  const code = await makeCode(page);
  const other = await newPhone(browser);
  await other.goto(`/join#${code}`);
  await expect(other.getByText(`${code.slice(0, 4)} ${code.slice(4)}`)).toBeVisible();
  await other
    .getByRole("button", { name: /^Sign in (on this phone|here in Safari instead)$/ })
    .click();
  await expect(other.getByRole("heading", { name: "Who’s using this phone?" })).toBeVisible();
  await expect(other).toHaveURL(/\/who$/);
  await other.context().close();
});

test("a typed code signs in a new phone, once", async ({ page, browser }) => {
  await signIn(page);
  const code = await makeCode(page);
  const other = await newPhone(browser);
  await other.goto("/sign-in");
  await other.getByRole("button", { name: "Use a code from another phone" }).click();
  await other
    .getByLabel("Code from another phone")
    .fill(`${code.slice(0, 4).toLowerCase()} ${code.slice(4)}`);
  await other.getByRole("button", { name: "Sign in" }).click();
  await expect(other.getByRole("heading", { name: "Who’s using this phone?" })).toBeVisible();
  await other.context().close();

  const third = await newPhone(browser);
  await third.goto("/sign-in");
  await third.getByRole("button", { name: "Use a code from another phone" }).click();
  await third.getByLabel("Code from another phone").fill(code);
  await third.getByRole("button", { name: "Sign in" }).click();
  await expect(third.getByRole("alert")).toContainText("That code didn't work.");
  await third.context().close();
});
