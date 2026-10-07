/**
 * M5 acceptance (docs/PLAN.md §12): zero serious or critical axe violations on every main screen
 * and sheet, in light and dark, at phone and desktop size. Lesser findings are printed for the
 * review. Synthetic data only.
 */
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

import { expect, openSettings, signIn, test } from "./fixtures";
import { api, seedTacoNight } from "./seed";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

/** iPhones zoom into any typing field under 16 px (ADR 0027): none may be smaller. */
async function typingFieldsAtLeast16px(page: Page, where: string): Promise<void> {
  const small = await page.evaluate(() =>
    Array.from(
      document.querySelectorAll(
        "input:not([type=checkbox]):not([type=radio]):not([type=file]):not([type=hidden]), select, textarea",
      ),
    )
      .filter((field) => {
        const box = field.getBoundingClientRect();
        return box.width > 1 && box.height > 1 && parseFloat(getComputedStyle(field).fontSize) < 16;
      })
      .map((field) => field.outerHTML.slice(0, 120)),
  );
  expect(small, `typing fields under 16 px on ${where}`).toEqual([]);
}

/** Every control a finger taps is at least 40 px each way (ADR 0027); links in a sentence aren't. */
async function targetsAtLeast40px(page: Page, where: string): Promise<void> {
  const small = await page.evaluate(() =>
    Array.from(document.querySelectorAll("button, a[href], [role=checkbox], summary, select"))
      .filter((control) => {
        if (control.closest("[inert], [aria-hidden='true']")) return false;
        const style = getComputedStyle(control);
        // A stretched button (a Plan card) covers its whole card with ::after: that's the target.
        const target = control.hasAttribute("data-stretched")
          ? (control.closest(".relative") ?? control)
          : control;
        const box = target.getBoundingClientRect();
        if (style.visibility === "hidden" || box.width <= 1 || box.height <= 1) return false;
        if (control.tagName === "A" && style.display === "inline") return false;
        return box.width < 40 || box.height < 40;
      })
      .map((control) => {
        const box = control.getBoundingClientRect();
        const text = control.textContent.trim().slice(0, 40);
        return `${control.tagName.toLowerCase()} "${text}" ${String(Math.round(box.width))}x${String(Math.round(box.height))}`;
      }),
  );
  expect(small, `targets under 40 px on ${where}`).toEqual([]);
}

async function check(page: Page, where: string): Promise<void> {
  await typingFieldsAtLeast16px(page, where);
  await targetsAtLeast40px(page, where);
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  // A11Y_ALL=1 fails on every finding, for a full review; normally only serious and critical.
  const blocking = results.violations.filter(
    (violation) =>
      process.env.A11Y_ALL === "1" ||
      violation.impact === "serious" ||
      violation.impact === "critical",
  );
  for (const violation of results.violations) {
    if (blocking.includes(violation)) continue;
    console.log(`${where}: ${violation.impact ?? "?"} ${violation.id}: ${violation.help}`);
  }
  expect(
    blocking.map(
      (violation) =>
        `${violation.id} (${violation.impact ?? "?"}): ${violation.help} → ${violation.nodes
          .map((node) => node.target.join(" "))
          .join(", ")}`,
    ),
    `axe on ${where}`,
  ).toEqual([]);
}

async function tab(page: Page, name: string, heading: string): Promise<void> {
  await page.getByRole("link", { name, exact: true }).click();
  await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
}

/** Tacos (with Rice) tonight and Chili, through the API; then the Plan shows them live. */
async function planned(page: Page): Promise<void> {
  const seeded = await seedTacoNight(page);
  const plan = (await (await page.request.get("/api/plan")).json()) as { today: string };
  await api(page, "POST", "/api/plan/meals", {
    main_id: seeded.tacos,
    side_ids: [seeded.riceSide],
    day: plan.today,
  });
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.chili });
  await api(page, "POST", "/api/plan/extras", { text: "Birthday candles", quantity: "1" });
  await expect(page.getByRole("list", { name: "This week's meals" })).toContainText("Chili");
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
    });

    test("before signing in", async ({ page }) => {
      await page.goto("/");
      const install = page.getByRole("button", { name: "Continue in Safari" });
      const password = page.getByLabel("Household password");
      await expect(install.or(password)).toBeVisible();
      if (await install.isVisible()) {
        await check(page, "install guide");
        await install.click();
      }
      await expect(password).toBeVisible();
      await check(page, "sign in");
      await page.getByRole("button", { name: "Use a code from another phone" }).click();
      await check(page, "sign in with a code");
    });

    test("planning", async ({ page }) => {
      await signIn(page);
      await planned(page);
      await check(page, "plan");

      await page.getByRole("button", { name: "Add a meal" }).click();
      await expect(page.getByRole("dialog", { name: "Add a meal" })).toBeVisible();
      await check(page, "add a meal");
      await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();

      await page.getByRole("button", { name: "Change Chili" }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await check(page, "change a meal");
      await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();

      await tab(page, "Meals", "Meals");
      await check(page, "meals");
      await page.getByRole("link", { name: /Tacos/ }).first().click();
      await expect(page.getByRole("heading", { name: "Tacos" })).toBeVisible();
      await check(page, "meal detail");

      await tab(page, "List", "Shopping list");
      await check(page, "list");
      await page
        .getByRole("button", { name: /Black beans/ })
        .first()
        .click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await check(page, "list line");
      await page.getByRole("dialog").getByRole("button", { name: "Rename Black beans" }).click();
      await expect(page.getByRole("dialog").getByLabel("What do you call it?")).toBeFocused();
      await check(page, "rename an item");
      await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();

      await page.getByRole("button", { name: "Add something else" }).click();
      const adding = page.getByRole("dialog", { name: "Add something else" });
      await adding.getByLabel("What do you need?").fill("cheese");
      await expect(adding.getByText("In your items as Shredded cheddar")).toBeVisible();
      await check(page, "add an item");
      await adding.getByRole("button", { name: /Sample Aged Gouda Cheese/ }).click();
      await expect(adding.getByLabel("What do you call it?")).toHaveValue("Cheese");
      await check(page, "name an item");
    });

    test("shopping and trips", async ({ page }) => {
      await signIn(page);
      await planned(page);
      await api(page, "POST", "/api/trips");
      await tab(page, "List", "Shopping list");
      await page.getByRole("button", { name: "Start shopping" }).click();
      await expect(page.getByTestId("progress")).toBeVisible();
      await check(page, "shopping");
      await page.getByRole("button", { name: /^Black beans/ }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await check(page, "shopping item");
      await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
      await page
        .getByRole("checkbox", { name: /^Check off/ })
        .first()
        .click();
      await expect(page.getByRole("button", { name: "Undo" })).toBeVisible();
      await check(page, "shopping, with a toast");
      await page.getByRole("button", { name: "Finish trip" }).click();
      await expect(page.getByRole("dialog", { name: "Finish trip" })).toBeVisible();
      await check(page, "finish trip");
      await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
    });

    test("settings, Kroger and adding a phone", async ({ page }) => {
      await signIn(page);
      await planned(page);
      await api(page, "POST", "/api/trips");
      await openSettings(page);
      await check(page, "settings");
      await page.getByRole("button", { name: "Change Sample Parent" }).click();
      await expect(page.getByRole("dialog", { name: "Change Sample Parent" })).toBeVisible();
      await check(page, "change a person");
      await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
      await page.getByRole("button", { name: "Connect Kroger" }).click();
      await expect(page.getByRole("heading", { name: "Demo sign-in" })).toBeVisible();
      await check(page, "demo sign-in");
      await page.getByRole("link", { name: "Allow", exact: true }).click();
      await expect(page.getByText("Kroger connected")).toBeVisible();
      await check(page, "settings, connected");

      await page.getByRole("button", { name: "Add a phone" }).click();
      await expect(page.getByTestId("join-code")).toBeVisible();
      await check(page, "add a phone");
      await page.getByRole("dialog").getByRole("button", { name: "Done" }).click();

      await tab(page, "List", "Shopping list");
      await page.getByRole("button", { name: "Send to Kroger cart" }).click();
      const sheet = page.getByRole("dialog", { name: "Send to Kroger cart" });
      await expect(sheet.getByRole("button", { name: /^Send \d+ items$/ })).toBeVisible();
      await check(page, "send to cart");
      await sheet.getByRole("button", { name: /^Send \d+ items$/ }).click();
      await expect(sheet.getByText(/^Added \d+ items to your Kroger cart\.$/)).toBeVisible();
      await check(page, "send to cart, sent");
      await sheet.getByRole("button", { name: "Close" }).click();

      await tab(page, "More", "More");
      await check(page, "more");
      await page.getByRole("link", { name: /Who’s using this/ }).click();
      await expect(page.getByRole("button", { name: /Using this phone/ })).toBeVisible();
      await check(page, "who's using this phone");
      await page.getByRole("button", { name: "Back" }).click();
      await page.getByRole("link", { name: "Trips" }).click();
      await expect(page.getByRole("heading", { name: "Trips" })).toBeVisible();
      await check(page, "trips");
      await page.getByRole("link", { name: "About & privacy" }).count(); // keep the tabs warm
    });
  });
}
