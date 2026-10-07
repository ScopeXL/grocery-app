/**
 * M3 acceptance (docs/PLAN.md §12, §9.8): shopping a saved list on phones, with and without
 * signal. Offline check-offs sync on reconnect, two phones converge, Undo works offline, the
 * latest action wins, late check-offs count after another phone finishes, and finishing
 * leads to Trips, Reopen and Shop this again. Synthetic data only.
 */
import type { BrowserContext, Page, Route } from "@playwright/test";

import { expect, PASSWORD, signIn, test } from "./fixtures";
import { api, seedTacoNight } from "./seed";

interface TripItem {
  id: string;
  name: string;
  state: string;
  state_by: string | null;
  note: string | null;
}

/** Plan Tacos (with Rice) and Chili, and save the list, through the API. */
async function savedTrip(page: Page): Promise<string> {
  const seeded = await seedTacoNight(page);
  await api(page, "POST", "/api/plan/meals", {
    main_id: seeded.tacos,
    side_ids: [seeded.riceSide],
  });
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.chili });
  const trip = await api(page, "POST", "/api/trips");
  return String(trip.id);
}

async function serverItems(page: Page, tripId: string): Promise<Record<string, TripItem>> {
  const response = await page.request.get(`/api/trips/${tripId}`);
  if (!response.ok()) return {}; // e.g. signed out a moment ago: polls simply try again
  const trip = (await response.json()) as { items: TripItem[] };
  return Object.fromEntries(trip.items.map((item) => [item.name, item]));
}

/** From the List tab, the way a person does it (no reloads mid-request). */
async function startShopping(page: Page): Promise<void> {
  await page.getByRole("link", { name: "List", exact: true }).click();
  await page.getByRole("button", { name: "Start shopping" }).click();
  await expect(page.getByTestId("progress")).toBeVisible();
}

async function checkOff(page: Page, name: string): Promise<void> {
  await page.getByRole("checkbox", { name: `Check off ${name}` }).click();
  await expect(page.getByText(`Checked off ${name}`)).toBeVisible();
}

async function secondPhone(
  browser: import("@playwright/test").Browser,
  name: string,
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await signIn(page, name);
  return { context, page };
}

test("offline check-offs are kept and match the server after reconnecting", async ({
  page,
  context,
}) => {
  await signIn(page);
  const tripId = await savedTrip(page);
  await startShopping(page);
  await expect(page.getByRole("region", { name: "Get ready for the store" })).toContainText(
    "Saved on this phone",
  );
  await expect(page.getByTestId("progress")).toHaveText("0 of 6");

  await context.setOffline(true);
  await checkOff(page, "Ground beef");
  await checkOff(page, "Taco shells");
  await checkOff(page, "Black beans");
  await page.getByRole("button", { name: /^Yellow onion/ }).click();
  const sheet = page.getByRole("dialog", { name: "Yellow onion" });
  await sheet.getByRole("button", { name: "Add a note" }).click();
  await sheet.getByLabel("Note for the shopper").fill("Ask at the produce desk");
  await sheet.getByRole("button", { name: "Save note" }).click();
  await page.getByRole("button", { name: /^Yellow onion/ }).click();
  await sheet.getByRole("button", { name: "Couldn’t find" }).click();

  await expect(page.getByTestId("progress")).toHaveText("4 of 6");
  // In the cart: beef 2 x $4.99 (sale) + shells $2.29 + beans 2 x $1.09 = $14.45.
  await expect(page.getByTestId("in-cart")).toContainText("In cart about $14");
  await expect(page.getByRole("status").filter({ hasText: "Offline" })).toBeVisible();

  await context.setOffline(false);
  await expect
    .poll(async () => {
      const items = await serverItems(page, tripId);
      return [
        items["Ground beef"]?.state,
        items["Taco shells"]?.state,
        items["Black beans"]?.state,
        items["Yellow onion"]?.state,
        items["Yellow onion"]?.note,
      ];
    })
    .toEqual(["done", "done", "done", "missed", "Ask at the produce desk"]);
  const items = await serverItems(page, tripId);
  expect(items["Ground beef"]?.state_by).not.toBeNull();
});

test("two phones shopping one list see each other's check-offs", async ({ page, browser }) => {
  await signIn(page, "Sample Parent");
  await savedTrip(page);
  const other = await secondPhone(browser, "Sample Kid");
  await startShopping(page);
  await startShopping(other.page);

  await checkOff(page, "Ground beef");
  await expect(other.page.getByTestId("progress")).toHaveText("1 of 6", { timeout: 3000 });
  await checkOff(other.page, "Taco shells");
  await expect(page.getByTestId("progress")).toHaveText("2 of 6", { timeout: 3000 });
  await other.context.close();
});

test("undo works with no signal and sends only the final answer", async ({ page, context }) => {
  await signIn(page);
  const tripId = await savedTrip(page);
  await startShopping(page);
  await context.setOffline(true);
  await checkOff(page, "Ground beef");
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByTestId("progress")).toHaveText("0 of 6");

  const sent: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith(`/api/trips/${tripId}/ops`)) sent.push(request.postData() ?? "");
  });
  await context.setOffline(false);
  await expect.poll(() => sent.length).toBeGreaterThan(0);
  const ops = sent.flatMap((body) => (JSON.parse(body) as { ops: unknown[] }).ops);
  expect(ops).toHaveLength(1); // the check-off and its undo compacted into one
  await expect
    .poll(async () => (await serverItems(page, tripId))["Ground beef"]?.state)
    .toBe("todo");
});

test("the latest action wins: an offline check-off doesn't undo a later couldn't-find", async ({
  page,
  context,
  browser,
}) => {
  await signIn(page, "Sample Parent");
  const tripId = await savedTrip(page);
  const other = await secondPhone(browser, "Sample Kid");
  await startShopping(page);
  await startShopping(other.page);

  await context.setOffline(true);
  await checkOff(page, "Black beans");
  await other.page.getByRole("button", { name: /^Black beans/ }).click();
  await other.page
    .getByRole("dialog", { name: "Black beans" })
    .getByRole("button", { name: "Couldn’t find" })
    .click();
  await expect
    .poll(async () => (await serverItems(other.page, tripId))["Black beans"]?.state)
    .toBe("missed");
  await context.setOffline(false);
  await expect(page.getByText("Couldn’t find (1)")).toBeVisible();
  expect((await serverItems(page, tripId))["Black beans"]?.state).toBe("missed");
  await other.context.close();
});

test("finish with what you paid, find it in Trips, reopen and shop it again", async ({ page }) => {
  await signIn(page);
  await savedTrip(page);
  await startShopping(page);
  await checkOff(page, "Ground beef");
  await page.getByRole("button", { name: "Finish trip" }).click();
  const finish = page.getByRole("dialog", { name: "Finish trip" });
  await finish.getByLabel("What did you pay? (optional)").fill("23.45");
  await finish.getByRole("button", { name: "Finish trip" }).click();
  await expect(page.getByRole("heading", { name: "Trips" })).toBeVisible();
  const finished = page.getByRole("region", { name: "Finished trips" });
  await expect(finished).toContainText("$23.45 paid");

  await finished.getByRole("link").first().click();
  await expect(page.getByRole("region", { name: "Bought", exact: true })).toContainText(
    "Ground beef",
  );

  // Reopen: back to shopping it, with what was already in the cart.
  await page.getByRole("button", { name: "Reopen" }).click();
  await expect(page.getByTestId("progress")).toHaveText("1 of 6");
  await page.getByRole("button", { name: "Finish trip" }).click();
  await page
    .getByRole("dialog", { name: "Finish trip" })
    .getByRole("button", { name: "Finish trip" })
    .click();
  await expect(page.getByRole("heading", { name: "Trips" })).toBeVisible();

  // Shop this again: a new saved list with the same items, all still to get.
  await page.getByRole("region", { name: "Finished trips" }).getByRole("link").first().click();
  await page.getByRole("button", { name: "Shop this again" }).click();
  await expect(page.getByTestId("progress")).toHaveText("0 of 6");
});

test("finishing with no signal syncs when the signal returns", async ({ page, context }) => {
  await signIn(page);
  const tripId = await savedTrip(page);
  await startShopping(page);
  await context.setOffline(true);
  await checkOff(page, "Ground beef");
  await page.getByRole("button", { name: "Finish trip" }).click();
  await page
    .getByRole("dialog", { name: "Finish trip" })
    .getByRole("button", { name: "Finish trip" })
    .click();
  await context.setOffline(false);
  await expect
    .poll(async () => {
      const response = await page.request.get(`/api/trips/${tripId}`);
      return ((await response.json()) as { status: string }).status;
    })
    .toBe("finished");
});

test("check-offs made offline still count after another phone finishes", async ({
  page,
  context,
  browser,
}) => {
  await signIn(page, "Sample Parent");
  const tripId = await savedTrip(page);
  const other = await secondPhone(browser, "Sample Kid");
  await startShopping(page);
  await startShopping(other.page);

  await context.setOffline(true);
  await checkOff(page, "Ground beef");
  await checkOff(page, "Taco shells");
  await other.page.getByRole("button", { name: "Finish trip" }).click();
  await other.page
    .getByRole("dialog", { name: "Finish trip" })
    .getByRole("button", { name: "Finish trip" })
    .click();
  await context.setOffline(false);

  await expect(page.getByRole("dialog", { name: "Trip finished" })).toContainText(
    "Sample Kid finished this trip.",
  );
  await expect(page.getByRole("dialog", { name: "Trip finished" })).toContainText(
    "Your 2 check-offs were saved.",
  );
  const items = await serverItems(page, tripId);
  expect([items["Ground beef"]?.state, items["Taco shells"]?.state]).toEqual(["done", "done"]);
  await other.context.close();
});

test("a dropped live connection loses nothing", async ({ page, browser }) => {
  await signIn(page, "Sample Parent");
  await savedTrip(page);
  const other = await secondPhone(browser, "Sample Kid");
  await startShopping(page);
  await startShopping(other.page);
  const dropped = await page.request.post("/api/_test/drop-streams", {
    headers: { "X-Dinner-Bell": "1" },
  });
  expect(dropped.status()).toBe(204);
  await checkOff(page, "Ground beef");
  await checkOff(page, "White rice");
  await expect(other.page.getByTestId("progress")).toHaveText("2 of 6", { timeout: 8000 });
  await other.context.close();
});

test("signed out mid-trip: taps wait, then go out after signing in", async ({ page }) => {
  await signIn(page);
  const tripId = await savedTrip(page);
  await startShopping(page);
  const revoked = await page.request.post("/api/_test/revoke-sessions", {
    headers: { "X-Dinner-Bell": "1" },
  });
  expect(revoked.status()).toBe(204);
  await checkOff(page, "Ground beef");
  await page.getByRole("link", { name: "Sign in to sync" }).click();
  await page.getByLabel("Household password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect
    .poll(async () => (await serverItems(page, tripId))["Ground beef"]?.state, { timeout: 10_000 })
    .toBe("done");
});

test("the screen stays on while shopping and lets go after finishing", async ({ page }) => {
  await page.addInitScript(() => {
    const calls: string[] = [];
    (window as unknown as { wakeCalls: string[] }).wakeCalls = calls;
    Object.defineProperty(navigator, "wakeLock", {
      configurable: true,
      value: {
        request: () => {
          calls.push("request");
          const sentinel = new EventTarget() as EventTarget & {
            released: boolean;
            release: () => Promise<void>;
          };
          sentinel.released = false;
          sentinel.release = () => {
            if (sentinel.released) return Promise.resolve();
            calls.push("release");
            sentinel.released = true;
            sentinel.dispatchEvent(new Event("release"));
            return Promise.resolve();
          };
          // Like a real browser: hiding the page lets go of the lock.
          document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "hidden") void sentinel.release();
          });
          return Promise.resolve(sentinel);
        },
      },
    });
  });
  await signIn(page);
  await savedTrip(page);
  await startShopping(page);
  const calls = () => page.evaluate(() => (window as unknown as { wakeCalls: string[] }).wakeCalls);
  await expect.poll(calls).toContain("request");
  await expect(page.getByText("Screen stays on").first()).toBeVisible();
  // Switch away and back: the lock is taken again.
  await page.evaluate(() => {
    const show = (state: string) => {
      Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
      document.dispatchEvent(new Event("visibilitychange"));
    };
    show("hidden");
    show("visible");
  });
  await expect
    .poll(async () => (await calls()).filter((call) => call === "request").length)
    .toBe(2);
  await page.getByRole("button", { name: "Finish trip" }).click();
  await page
    .getByRole("dialog", { name: "Finish trip" })
    .getByRole("button", { name: "Finish trip" })
    .click();
  await expect.poll(calls).toContain("release");
});

test("a phone whose clock runs fast still can't overrule a later action", async ({
  page,
  context,
  browser,
}) => {
  await page.clock.install({ time: new Date(Date.now() + 10 * 60_000) }); // 10 minutes fast
  await signIn(page, "Sample Parent");
  const tripId = await savedTrip(page);
  const other = await secondPhone(browser, "Sample Kid");
  await startShopping(page);
  await startShopping(other.page);

  await context.setOffline(true);
  await checkOff(page, "Black beans"); // stamped with corrected time, not the fast clock
  await other.page.getByRole("button", { name: /^Black beans/ }).click();
  await other.page
    .getByRole("dialog", { name: "Black beans" })
    .getByRole("button", { name: "Couldn’t find" })
    .click();
  await expect
    .poll(async () => (await serverItems(other.page, tripId))["Black beans"]?.state)
    .toBe("missed");
  await context.setOffline(false);
  await expect(page.getByText("Couldn’t find (1)")).toBeVisible();
  expect((await serverItems(page, tripId))["Black beans"]?.state).toBe("missed");
  await other.context.close();
});

test("trying again puts a couldn't-find item back and keeps its note", async ({ page }) => {
  await signIn(page);
  const tripId = await savedTrip(page);
  await startShopping(page);
  const sheet = page.getByRole("dialog", { name: "White rice" });
  await page.getByRole("button", { name: /^White rice/ }).click();
  await sheet.getByRole("button", { name: "Add a note" }).click();
  await sheet.getByLabel("Note for the shopper").fill("Brown is fine too");
  await sheet.getByRole("button", { name: "Save note" }).click();
  await page.getByRole("button", { name: /^White rice/ }).click();
  await sheet.getByRole("button", { name: "Couldn’t find" }).click();
  await expect(page.getByText("Couldn’t find (1)")).toBeVisible();

  await page.getByRole("button", { name: /^White rice/ }).click();
  await sheet.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("Couldn’t find (1)")).toBeHidden();
  await expect(page.getByRole("button", { name: /^White rice/ })).toContainText(
    "Brown is fine too",
  );
  await expect
    .poll(async () => {
      const rice = (await serverItems(page, tripId))["White rice"];
      return [rice?.state, rice?.note];
    })
    .toEqual(["todo", "Brown is fine too"]);
});

test("saved with signal, opened without: still ready for the store", async ({ page, context }) => {
  await signIn(page);
  const seeded = await seedTacoNight(page);
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.tacos });
  await page.getByRole("link", { name: "List", exact: true }).click();
  await page.getByRole("button", { name: "Save list" }).click();
  await expect(page.getByRole("button", { name: "Start shopping" })).toBeVisible();

  await context.setOffline(true);
  await page.getByRole("button", { name: "Start shopping" }).click();
  const ready = page.getByRole("region", { name: "Get ready for the store" });
  await expect(ready).toContainText("Ready for the store");
  await expect(ready).toContainText("Saved on this phone");
  await checkOff(page, "Ground beef");
  await expect(page.getByTestId("progress")).toHaveText("1 of 3");
});

test("a row checked here folds out of its aisle into Done; its checkbox is a big target", async ({
  page,
}) => {
  await signIn(page);
  await savedTrip(page);
  await startShopping(page);
  const box = page.getByRole("checkbox", { name: "Check off Ground beef" });
  const size = await box.boundingBox();
  expect(size?.width).toBeGreaterThanOrEqual(48);
  expect(size?.height).toBeGreaterThanOrEqual(48);

  await box.click();
  const checked = page.getByRole("checkbox", { name: "Uncheck Ground beef" });
  await expect(checked).toBeVisible(); // in its aisle while the stroke draws
  await expect(page.getByText("Done (1)")).toBeVisible();
  await expect(checked).toBeHidden(); // folded away, into the closed Done list
  await page.getByText("Done (1)").click();
  await expect(checked).toBeVisible();
});

test("a trip just finished shows as finished, even before the server hears", async ({ page }) => {
  await signIn(page);
  await savedTrip(page);
  await startShopping(page);
  await checkOff(page, "Ground beef");
  // Hold what this phone sends, as on a weak signal. (WebKit may let it through: a page its
  // service worker controls can skip routing. Chromium holds it.)
  const held: Route[] = [];
  let holding = true;
  await page.route("**/api/trips/*/ops", async (route) => {
    if (holding) held.push(route);
    else await route.continue();
  });
  await page.getByRole("button", { name: "Finish trip" }).click();
  await page
    .getByRole("dialog", { name: "Finish trip" })
    .getByRole("button", { name: "Finish trip" })
    .click();
  await expect(page.getByRole("heading", { name: "Trips" })).toBeVisible();
  await page.getByRole("region", { name: "Finished trips" }).getByRole("link").first().click();
  await expect(page.getByRole("button", { name: "Shop this again" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start shopping" })).toHaveCount(0);
  holding = false;
  for (const route of held) await route.continue();
  await page.unroute("**/api/trips/*/ops");
});
