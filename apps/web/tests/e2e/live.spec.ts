import { test, expect } from "@playwright/test";

test.describe("Live Backend Integration Specs", () => {
  test.skip(!process.env.E2E_LIVE, "Skipped unless E2E_LIVE=1 is set");

  test("live login: logs in with reviewer@gigbid.local and verifies header email", async ({ page }) => {
    await page.goto("/login");

    const emailInput = page.locator('[data-testid="login-email-input"]');
    const passwordInput = page.locator('[data-testid="login-password-input"]');
    const submitBtn = page.locator('[data-testid="login-submit-button"]');

    await emailInput.fill(process.env.REVIEWER_EMAIL || "reviewer@gigbid.local");
    await passwordInput.fill(process.env.REVIEWER_PASSWORD || "replace_me_reviewer_password");
    await submitBtn.click();

    // Verify redirected to inbox and header displays actual reviewer email
    await page.waitForURL("**/inbox");
    const userEmail = page.locator('[data-testid="navbar-user-email"]');
    await expect(userEmail).toBeVisible({ timeout: 10000 });
    await expect(userEmail).toContainText("reviewer@gigbid.local");
  });

  test("live inbox: loads /inbox and asserts at least one real job_ id is visible", async ({ page }) => {
    // Authenticate first
    await page.goto("/login");
    await page.locator('[data-testid="login-email-input"]').fill(process.env.REVIEWER_EMAIL || "reviewer@gigbid.local");
    await page.locator('[data-testid="login-password-input"]').fill(process.env.REVIEWER_PASSWORD || "replace_me_reviewer_password");
    await page.locator('[data-testid="login-submit-button"]').click();
    await page.waitForURL("**/inbox");

    // Wait for jobs to load
    const jobCards = page.locator('[data-testid^="job-card-job_"]');
    await expect(jobCards.first()).toBeVisible({ timeout: 15000 });

    const count = await jobCards.count();
    expect(count).toBeGreaterThanOrEqual(1);

    // Assert that the first job card ID starts with job_
    const firstTestId = await jobCards.first().getAttribute("data-testid");
    expect(firstTestId).toMatch(/^job-card-job_/);
  });
});
