import { test, expect } from "@playwright/test";

test.describe("Proposal Studio Rejection with Mandatory Reason", () => {
  test("enforces rejection feedback requirement before enabling reject confirmation", async ({ page }) => {
    await page.goto("/studio/job_002");

    // Click reject proposal toggle
    const toggleBtn = page.locator('[data-testid="toggle-reject-button"]');
    await toggleBtn.click();

    // Rejection box should be visible
    const rejectBox = page.locator('[data-testid="rejection-box"]');
    await expect(rejectBox).toBeVisible();

    const confirmBtn = page.locator('[data-testid="confirm-reject-button"]');
    const reasonTextarea = page.locator('[data-testid="rejection-reason-textarea"]');

    // Confirm button must be disabled initially
    await expect(confirmBtn).toBeDisabled();

    // Type rejection reason
    await reasonTextarea.fill("Client project scope is ambiguous regarding legacy database schema.");

    // Confirm button must now be enabled
    await expect(confirmBtn).toBeEnabled();

    // Click confirm rejection
    await confirmBtn.click();

    // Verify rejection badge displays typed reason
    const badge = page.locator('[data-testid="rejection-success-badge"]');
    await expect(badge).toBeVisible();
    await expect(badge).toContainText("Client project scope is ambiguous regarding legacy database schema.");
  });
});
