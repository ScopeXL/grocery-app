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

/** Sign in from a fresh browser, passing the iPhone install guide if it appears. */
export async function signIn(page: Page, name = "Sample Parent"): Promise<void> {
  await page.goto("/");
  const continueInSafari = page.getByRole("button", { name: "Continue in Safari" });
  const password = page.getByLabel("Household password");
  await expect(continueInSafari.or(password)).toBeVisible();
  if (await continueInSafari.isVisible()) await continueInSafari.click();
  await expect(password).toBeVisible();
  await password.fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Who’s using this phone?" })).toBeVisible();
  const existing = page.getByRole("button", { name });
  if (await existing.count()) {
    await existing.click();
  } else {
    const someoneElse = page.getByRole("button", { name: "Someone else" });
    if (await someoneElse.count()) await someoneElse.click();
    await page.getByLabel("Your name").fill(name);
    await page.getByRole("button", { name: "Add me" }).click();
  }
  await expect(page.getByRole("heading", { name: "This week" })).toBeVisible();
}
