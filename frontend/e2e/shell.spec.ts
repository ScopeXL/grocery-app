import { expect, openSettings, signIn, test } from "./fixtures";
import { api, seedTacoNight } from "./seed";

test("every tab teaches what goes there", async ({ page }) => {
  await signIn(page);
  await expect(page.getByText("No meals planned yet.")).toBeVisible();
  await page.getByRole("link", { name: "Meals" }).click();
  await expect(page.getByText("Your meals live here.")).toBeVisible();
  await page.getByRole("link", { name: "List" }).click();
  await expect(page.getByText("Your list fills in as you plan meals.")).toBeVisible();
  await page.getByRole("link", { name: "More" }).click();
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
});

test("nothing scrolls sideways at phone width", async ({ page, isMobile }) => {
  test.skip(!isMobile, "phone only");
  await signIn(page);
  // Move the way a person does (in-app links), not by reloading the page between screens.
  const screens: [link: string | null, heading: string][] = [
    [null, "This week"],
    ["Meals", "Meals"],
    ["New meal", "New meal"],
    ["Meals", "Meals"],
    ["List", "Shopping list"],
    ["More", "More"],
    ["Settings", "Settings"],
    ["More", "More"],
    ["About & privacy", "About"],
  ];
  for (const [link, heading] of screens) {
    if (link === "New meal") await page.getByRole("button", { name: link }).click();
    else if (link) await page.getByRole("link", { name: link, exact: true }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(heading);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `horizontal overflow on ${heading}`).toBeLessThanOrEqual(0);
  }
});

test("settings shows the version and a live connection", async ({ page }) => {
  await signIn(page);
  await openSettings(page);
  await expect(page.getByTestId("version")).toContainText("Version");
  await expect(page.getByTestId("live-status")).toHaveText("Live updates: connected");
});

test("a change on one phone appears on another without refreshing", async ({ page, browser }) => {
  await signIn(page, "Sample Parent");
  const other = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const otherPage = await other.newPage();
  await signIn(otherPage, "Sample Kid");
  await openSettings(page);
  await expect(page.getByTestId("live-status")).toHaveText("Live updates: connected");
  await openSettings(otherPage);
  await otherPage.getByLabel("Add a person").fill("Mia");
  await otherPage.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Mia", { exact: true })).toBeVisible({ timeout: 3000 });
  await other.close();
});

test("removing a person can be undone", async ({ page }) => {
  await signIn(page);
  await openSettings(page);
  await page.getByLabel("Add a person").fill("Mia");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Change Mia" }).click();
  await page
    .getByRole("dialog", { name: "Change Mia" })
    .getByRole("button", { name: "Remove Mia" })
    .click();
  await expect(page.getByText("Removed Mia")).toBeVisible();
  await expect(page.getByRole("button", { name: "Change Mia" })).toHaveCount(0);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: "Change Mia" })).toBeVisible();
});

test("a toast's Undo can be tapped while a sheet is open", async ({ page }) => {
  await signIn(page);
  const seeded = await seedTacoNight(page);
  await api(page, "POST", "/api/plan/meals", { main_id: seeded.tacos });
  await api(page, "POST", "/api/plan/extras", { item_id: seeded.cheddar, quantity: "1" });
  await page.getByRole("link", { name: "List", exact: true }).click();
  await page.getByRole("button", { name: /^Shredded cheddar/ }).click();
  const sheet = page.getByRole("dialog", { name: "Shredded cheddar" });
  await sheet.getByRole("button", { name: "Remove" }).click();
  await expect(sheet.getByText("Added outside meals")).toBeHidden();
  // The toast shows in the sheet: the page behind it can't be tapped.
  await sheet.getByRole("button", { name: "Undo" }).click();
  await expect(sheet.getByText("Added outside meals")).toBeVisible();
});

test("a person's name and color can be changed, and Undo puts them back", async ({ page }) => {
  await signIn(page);
  await openSettings(page);
  await page.getByLabel("Add a person").fill("Mia");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Change Mia" }).click();
  const sheet = page.getByRole("dialog", { name: "Change Mia" });
  await sheet.getByLabel("Name").fill("Sample Teen");
  await sheet.getByRole("radio", { name: "Plum" }).check();
  await sheet.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Changes saved")).toBeVisible();
  await expect(page.getByRole("button", { name: "Change Sample Teen" })).toBeVisible();
  const members = async () =>
    (
      (await (await page.request.get("/api/members")).json()) as {
        name: string;
        marker_color: string;
      }[]
    ).map((member) => `${member.name}: ${member.marker_color}`);
  expect(await members()).toContain("Sample Teen: plum");

  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: "Change Mia" })).toBeVisible();
  expect(await members()).not.toContain("Sample Teen: plum");
});
