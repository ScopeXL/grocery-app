import { expect, test as base, type APIRequestContext, type Page } from "@playwright/test";

export const PASSWORD = "e2e-household-passphrase";

/**
 * Every test: a fresh server state, and a guard that fails the test on any CSP violation,
 * uncaught page error or browser dialog ("never an error wall").
 */
export const test = base.extend<{ cspGuard: boolean; guard: undefined }>({
  cspGuard: [true, { option: true }],
  guard: [
    async ({ page, request, cspGuard }, use) => {
      await resetServer(request);
      const problems: string[] = [];
      page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
      page.on("dialog", (dialog) => {
        problems.push(`dialog: ${dialog.message()}`);
        void dialog.dismiss();
      });
      await page.addInitScript(() => {
        document.addEventListener("securitypolicyviolation", (event) => {
          console.error(`CSP violation: ${event.violatedDirective} ${event.blockedURI}`);
        });
      });
      page.on("console", (message) => {
        if (cspGuard && message.text().startsWith("CSP violation")) problems.push(message.text());
      });
      await use(undefined);
      expect(problems, "no CSP violations, page errors or dialogs").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

export async function resetServer(request: APIRequestContext): Promise<void> {
  const response = await request.post("/api/_test/reset", { headers: { "X-Dinner-Bell": "1" } });
  expect(response.status()).toBe(204);
}

/** The fake Kroger's first store (synthetic). */
export const SAMPLE_STORE = "99999001";

/**
 * Sign in from a fresh browser, passing the iPhone install guide if it appears. Unless asked
 * not to, the household's store is chosen first (through the API), so the tabs open instead of
 * the first-run steps.
 */
export async function signIn(
  page: Page,
  name = "Sample Parent",
  { withStore = true }: { withStore?: boolean } = {},
): Promise<void> {
  await page.goto("/");
  const continueInSafari = page.getByRole("button", { name: "Continue in Safari" });
  const password = page.getByLabel("Household password");
  await expect(continueInSafari.or(password)).toBeVisible();
  if (await continueInSafari.isVisible()) await continueInSafari.click();
  await expect(password).toBeVisible();
  await password.fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Who’s using this phone?" })).toBeVisible();
  if (withStore) await chooseStore(page);
  const existing = page.getByRole("button", { name });
  if (await existing.count()) {
    await existing.click();
  } else {
    const someoneElse = page.getByRole("button", { name: "Someone else" });
    if (await someoneElse.count()) await someoneElse.click();
    await page.getByLabel("Your name").fill(name);
    await page.getByRole("button", { name: "Add me" }).click();
  }
  await expect(
    page.getByRole("heading", { name: withStore ? "This week" : "Choose your store" }),
  ).toBeVisible();
}

/** Choose the sample store with the page's own session (no UI). */
export async function chooseStore(page: Page): Promise<void> {
  const response = await page.request.put("/api/stores/active", {
    data: { location_id: SAMPLE_STORE },
    headers: { "X-Dinner-Bell": "1" },
  });
  expect(response.status()).toBe(200);
}

/** More → Settings with in-app links: a page.goto mid-request is a page error on WebKit. */
export async function openSettings(page: Page): Promise<void> {
  await page.getByRole("link", { name: "More", exact: true }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
}
