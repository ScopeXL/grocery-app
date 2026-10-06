import { expect, signIn, test } from "./fixtures";

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
  await page.goto("/settings");
  await expect(page.getByTestId("version")).toContainText("Version");
  await expect(page.getByTestId("live-status")).toHaveText("Live updates: connected");
});

test("a change on one phone appears on another without refreshing", async ({ page, browser }) => {
  await signIn(page, "Sample Parent");
  const other = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const otherPage = await other.newPage();
  await signIn(otherPage, "Sample Kid");
  await page.goto("/settings");
  await expect(page.getByTestId("live-status")).toHaveText("Live updates: connected");
  await otherPage.goto("/settings");
  await otherPage.getByLabel("Add a person").fill("Mia");
  await otherPage.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Mia", { exact: true })).toBeVisible({ timeout: 3000 });
  await other.close();
});

test("removing a person can be undone", async ({ page }) => {
  await signIn(page);
  await page.goto("/settings");
  await page.getByLabel("Add a person").fill("Mia");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Remove Mia" }).click();
  await expect(page.getByText("Removed Mia")).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: "Remove Mia" })).toBeVisible();
});
