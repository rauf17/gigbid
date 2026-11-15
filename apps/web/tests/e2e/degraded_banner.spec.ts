import { test, expect } from "@playwright/test";

test.describe("Degraded Mode Banner", () => {
  test("displays degraded mode banner when system health reports 503 or degraded status", async ({ page }) => {
    await page.goto("/inbox?degraded=1");

    const banner = page.locator('[data-testid="degraded-mode-banner"]');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("System Degraded Mode Active (HTTP 503)");

    // Dismiss banner
    await banner.locator("button").click();
    await expect(banner).not.toBeVisible();
  });
});
