/**
 * Captures the key screens for review (`just screenshots`): phone and desktop, light and dark.
 * Fake mode only; files go to the gitignored .screenshots/ folder (CLAUDE.md rule 1).
 */
import { expect, signIn, test } from "./fixtures";

// Playwright's WebKit screenshot code injects an inline <style>, which our CSP blocks and
// reports. Every other spec keeps the CSP guard on, so real violations are still caught.
test.use({ cspGuard: false });

const SCREENS = [
  { name: "plan", path: "/", heading: "This week" },
  { name: "meals", path: "/meals", heading: "Meals" },
  { name: "list", path: "/list", heading: "Shopping list" },
  { name: "more", path: "/more", heading: "More" },
  { name: "settings", path: "/settings", heading: "Settings" },
  { name: "about", path: "/about", heading: "About & privacy" },
];

for (const scheme of ["light", "dark"] as const) {
  test(`@screenshots ${scheme}`, async ({ page }, testInfo) => {
    test.skip(!process.env.SCREENSHOTS, "run with `just screenshots`");
    await page.emulateMedia({ colorScheme: scheme });
    const dir = `../.screenshots/${testInfo.project.name}`;
    await page.goto("/sign-in");
    await expect(page.getByLabel("Household password")).toBeVisible();
    await page.screenshot({ path: `${dir}/sign-in-${scheme}.png`, caret: "initial" });
    await page.goto("/install?from=more");
    await expect(
      page.getByRole("heading", { name: "Put Dinner Bell on your home screen" }),
    ).toBeVisible();
    await page.screenshot({
      path: `${dir}/install-${scheme}.png`,
      fullPage: true,
      caret: "initial",
    });
    await signIn(page);
    await page.goto("/who");
    await expect(page.getByRole("heading", { name: "Who’s using this phone?" })).toBeVisible();
    await page.screenshot({ path: `${dir}/who-${scheme}.png`, caret: "initial" });
    for (const screen of SCREENS) {
      await page.goto(screen.path);
      await expect(page.getByRole("heading", { name: screen.heading, exact: true })).toBeVisible();
      await page.screenshot({
        path: `${dir}/${screen.name}-${scheme}.png`,
        fullPage: true,
        // The default caret: "hide" injects an inline <style>, which our CSP rightly blocks.
        caret: "initial",
      });
    }
  });
}
