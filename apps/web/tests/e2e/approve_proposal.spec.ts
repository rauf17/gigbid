import { test, expect } from "@playwright/test";

test.describe("Proposal Studio Approval", () => {
  test("approves an evidence-grounded proposal and transitions to submitted", async ({ page }) => {
    await page.goto("/studio/job_001");

    // Check studio loaded
    await expect(page.locator("h1")).toContainText("Production Time-Series Forecasting Pipeline with LightGBM");

    // Initial status badge is draft
    const statusBadge = page.locator('[data-testid="proposal-status-badge"]');
    await expect(statusBadge).toContainText("draft");

    // Click Approve button
    const approveBtn = page.locator('[data-testid="approve-proposal-button"]');
    await expect(approveBtn).toBeEnabled();
    await approveBtn.click();

    // Verify status changes to submitted and success message visible
    await expect(page.locator('[data-testid="approval-success-badge"]')).toBeVisible();
    await expect(statusBadge).toContainText("submitted");
  });
});
