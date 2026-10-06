import { expect, signIn, test } from "./fixtures";

test.use({ serviceWorkers: "allow" });

test("the app opens with no signal and shows only a quiet offline pill", async ({
  page,
  context,
  browserName,
}) => {
  test.skip(browserName !== "chromium", "service-worker tests run on Chromium");
  await signIn(page);
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload(); // now controlled by the service worker
  await expect(page.getByRole("heading", { name: "This week" })).toBeVisible();
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { name: "This week" })).toBeVisible();
  await page.getByRole("link", { name: "More" }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("status").getByText("Offline")).toBeVisible({ timeout: 6000 });
  await context.setOffline(false);
});
