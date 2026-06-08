import { test, expect } from "@playwright/test";

const realAuth = process.env.E2E_REAL_AUTH === "true";

test.describe("dashboard", () => {
  test.skip(!realAuth, "E2E_REAL_AUTH=true required to run against a live Auth0 dev tenant");

  test("sign-in lands on dashboard", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /sign in/i }).click();
    await page.waitForURL("**/dashboard*");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});
