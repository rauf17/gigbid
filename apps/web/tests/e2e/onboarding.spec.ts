import { test, expect } from "@playwright/test";

test.describe("Onboarding Flow", () => {
  test("allows selecting a freelancer persona and navigates to inbox", async ({ page }) => {
    await page.goto("/onboarding");

    // Check header
    await expect(page.locator("h1")).toContainText("Select Your Freelance Persona");

    // Select Fullstack persona card
    const fullstackCard = page.locator('[data-testid="persona-card-fullstack"]');
    await expect(fullstackCard).toBeVisible();
    await fullstackCard.click();

    // Click continue
    const continueBtn = page.locator('[data-testid="onboarding-continue-button"]');
    await continueBtn.click();

    // Verify redirected to inbox
    await page.waitForURL("**/inbox");
    await expect(page.locator("h1")).toContainText("Opportunity Inbox");
  });
});
