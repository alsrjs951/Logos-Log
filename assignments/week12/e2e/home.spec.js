const { test, expect } = require('@playwright/test');

test.describe('Logos-Log Mock Portal E2E Flow', () => {

  test('should load portal, verify structure and trigger feature flag message', async ({ page }) => {
    // 1. Visit the baseURL (http://localhost:3050) served by mock server
    await page.goto('/');
    
    // 2. Validate page title and heading
    await expect(page).toHaveTitle('Logos-Log Mock Portal');
    
    const heading = page.locator('h1');
    await expect(heading).toHaveText('Welcome to Logos-Log E2E Portal');
    
    // 3. Verify that the result message is initially empty
    const message = page.locator('#result-message');
    await expect(message).toBeEmpty();
    
    // 4. Click the button to trigger feature flag action
    const btn = page.locator('#toggle-flag');
    await btn.click();
    
    // 5. Verify the updated message text
    await expect(message).toHaveText('Feature Flag Active!');
  });
});
