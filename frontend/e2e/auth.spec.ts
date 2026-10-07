import { expect, openSettings, signIn, test } from "./fixtures";

test("iPhone in Safari sees the install guide before signing in", async ({
  page,
  isMobile,
  browserName,
}) => {
  test.skip(!(isMobile && browserName === "webkit"), "iPhone only");
  await page.goto("/");
  await expect(page).toHaveURL(/\/install$/);
  await expect(
    page.getByRole("heading", { name: "Put Dinner Bell on your home screen" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Continue in Safari" }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
});

test("a wrong password says exactly what to do", async ({ page }) => {
  await page.goto("/sign-in");
  await page.getByLabel("Household password").fill("not the password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toHaveText("That password didn't match. Try again.");
});

test("sign in, pick your name, and stay signed in", async ({ page }) => {
  await signIn(page);
  await page.reload();
  await expect(page.getByRole("heading", { name: "This week" })).toBeVisible();
  await page.getByRole("link", { name: "More" }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByText("Used by Sample Parent")).toBeVisible();
});

test("signing out returns to the sign-in screen", async ({ page }) => {
  await signIn(page);
  await openSettings(page);
  await page.getByRole("button", { name: "Sign out of this phone" }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
  await page.goto("/");
  await expect(page).toHaveURL(/\/(sign-in|install)$/);
});
