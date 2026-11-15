import { test, expect } from "@playwright/test";

test.describe("Proposal Studio Draft Editing and Compliance Gating", () => {
  test("flags compliance violation when editing draft with off-platform contact", async ({ page }) => {
    await page.goto("/studio/job_001");

    // Click Edit Draft button
    const editBtn = page.locator('[data-testid="edit-draft-button"]');
    await editBtn.click();

    const textarea = page.locator('[data-testid="proposal-edit-textarea"]');
    await expect(textarea).toBeVisible();

    // Insert an off-platform policy violation (Telegram handle)
    await textarea.fill("I can complete this immediately. Contact me on telegram @fast_crypto_worker for payment.");
    await page.locator('[data-testid="save-edit-button"]').click();

    // Compliance violation warning banner must appear
    const alert = page.locator('[data-testid="compliance-violation-alert"]');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("Off-platform contact or payment prohibited by policy");

    // Edit again with compliant text
    await page.locator('[data-testid="edit-draft-button"]').click();
    await textarea.fill("I can complete this pipeline using FastAPI and PostgreSQL containerized cleanly in Docker.");
    await page.locator('[data-testid="save-edit-button"]').click();

    // Compliance alert should now be gone
    await expect(alert).not.toBeVisible();
  });
});
