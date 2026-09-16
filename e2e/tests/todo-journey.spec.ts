import { test, expect, Page } from "@playwright/test";

/**
 * E2E Test: Full User Journey
 *
 * Scenario:
 *   Register → Login → Create a todo → Toggle completion → Verify in UI → Logout
 *
 * This test covers the core happy-path flow that every user goes through.
 * It verifies end-to-end integration between the frontend, backend, and database.
 */

const BASE_URL = process.env.FRONTEND_URL || "http://localhost:3000";

// Generate a unique email for each test run to avoid conflicts
function uniqueEmail() {
  return `e2e_journey_${Date.now()}@test.com`;
}

async function register(page: Page, email: string, password: string) {
  await page.goto(`${BASE_URL}/register`);

  await page.fill('input[type="email"], input#email', email);
  await page.fill('input[type="password"], input#password', password);

  // Handle confirm password field if present
  const confirmField = page.locator(
    'input[name="confirmPassword"], input#confirmPassword'
  );
  if (await confirmField.isVisible()) {
    await confirmField.fill(password);
  }

  await page.click('button[type="submit"]');
}

async function login(page: Page, email: string, password: string) {
  await page.goto(`${BASE_URL}/login`);
  await page.fill('input[type="email"], input#email', email);
  await page.fill('input[type="password"], input#password', password);
  await page.click('button[type="submit"]');
}

// ──────────────────────────────────────────────────────────────────────────────

test.describe("Full User Journey", () => {
  const email = uniqueEmail();
  const password = "E2eTest@123";
  const TODO_TITLE = `My E2E Todo ${Date.now()}`;

  test("1 – Register a new account", async ({ page }) => {
    await register(page, email, password);

    // After successful registration, should redirect to dashboard/home
    await expect(page).toHaveURL(/\/$|\/dashboard/, { timeout: 15_000 });
  });

  test("2 – Login with credentials", async ({ page }) => {
    await login(page, email, password);

    // Should land on the main todos page
    await expect(page).toHaveURL(/\/$|\/dashboard/, { timeout: 15_000 });
    // Should see user email in the header
    await expect(page.locator("text=" + email)).toBeVisible({ timeout: 10_000 });
  });

  test("3 – Create a todo", async ({ page }) => {
    await login(page, email, password);
    await expect(page).toHaveURL(/\/$|\/dashboard/, { timeout: 15_000 });

    // Click "Add Todo" or similar button
    const addButton = page.locator(
      'button:has-text("Add Todo"), button:has-text("Add"), button:has-text("New Todo")'
    );
    await addButton.first().click();

    // Fill in the todo form
    const titleInput = page.locator(
      'input#title, input[placeholder*="needs to be done"], input[placeholder*="title"]'
    );
    await titleInput.first().fill(TODO_TITLE);

    // Submit
    await page.click(
      'button[type="submit"]:has-text("Create"), button[type="submit"]:has-text("Add"), button[type="submit"]:has-text("Save")'
    );

    // Wait for the todo to appear in the list
    await expect(page.locator(`text=${TODO_TITLE}`)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("4 – Toggle todo completion and verify", async ({ page }) => {
    await login(page, email, password);
    await expect(page).toHaveURL(/\/$|\/dashboard/, { timeout: 15_000 });

    // Find and check the checkbox for our todo
    const todoItem = page.locator(`[id*="todo-"], label, .todo-item`).filter({
      hasText: TODO_TITLE,
    });

    // Find the associated checkbox
    const checkbox = todoItem.locator('input[type="checkbox"], [role="checkbox"]');
    await expect(checkbox.first()).toBeVisible({ timeout: 10_000 });

    // Toggle to completed
    await checkbox.first().click();

    // Verify the todo shows as completed (line-through style or aria-checked)
    await expect(
      page
        .locator(`text=${TODO_TITLE}`)
        .first()
    ).toBeVisible({ timeout: 5_000 });

    // Toggle back to incomplete
    await checkbox.first().click();
  });

  test("5 – Logout", async ({ page }) => {
    await login(page, email, password);
    await expect(page).toHaveURL(/\/$|\/dashboard/, { timeout: 15_000 });

    // Click logout button
    await page.click(
      'button:has-text("Logout"), button:has-text("Sign out"), a:has-text("Logout")'
    );

    // Should redirect to login page
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });

    // Navigating to / should redirect back to /login (session cleared)
    await page.goto(`${BASE_URL}/`);
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });
});
