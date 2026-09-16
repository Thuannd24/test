import { test, expect, Page, BrowserContext } from "@playwright/test";

/**
 * E2E Test: Cross-User Data Isolation
 *
 * Scenario:
 *   User A creates a PRIVATE todo → User B logs in on a SEPARATE session →
 *   User B must NOT see User A's todo.
 *
 * This test verifies that the todo list API properly filters by the
 * authenticated user (authorization boundary / IDOR prevention).
 */

const BASE_URL = process.env.FRONTEND_URL || "http://localhost:3000";

function uniqueEmail(role: string) {
  return `e2e_isolation_${role}_${Date.now()}@test.com`;
}

async function registerAndLogin(
  context: BrowserContext,
  email: string,
  password: string
): Promise<Page> {
  const page = await context.newPage();

  // Register
  await page.goto(`${BASE_URL}/register`);
  await page.fill('input[type="email"], input#email', email);
  await page.fill('input[type="password"], input#password', password);

  const confirmField = page.locator(
    'input[name="confirmPassword"], input#confirmPassword'
  );
  if (await confirmField.isVisible()) {
    await confirmField.fill(password);
  }
  await page.click('button[type="submit"]');

  // Wait for redirect to dashboard
  await expect(page).toHaveURL(/\/$|\/dashboard/, { timeout: 15_000 });

  return page;
}

// ──────────────────────────────────────────────────────────────────────────────

test.describe("Cross-User Data Isolation", () => {
  const PASSWORD = "Isolation@123";
  const emailA = uniqueEmail("userA");
  const emailB = uniqueEmail("userB");
  const PRIVATE_TODO_TITLE = `UserA Private Todo ${Date.now()}`;

  test("User A creates a private todo; User B cannot see it", async ({
    browser,
  }) => {
    // ── User A Session ──────────────────────────────────────────────────────
    const contextA = await browser.newContext();
    const pageA = await registerAndLogin(contextA, emailA, PASSWORD);

    // User A creates a todo
    const addButton = pageA.locator(
      'button:has-text("Add Todo"), button:has-text("Add"), button:has-text("New Todo")'
    );
    await addButton.first().click();

    const titleInput = pageA.locator(
      'input#title, input[placeholder*="needs to be done"], input[placeholder*="title"]'
    );
    await titleInput.first().fill(PRIVATE_TODO_TITLE);

    await pageA.click(
      'button[type="submit"]:has-text("Create"), button[type="submit"]:has-text("Add"), button[type="submit"]:has-text("Save")'
    );

    // Wait for the todo to appear for User A
    await expect(pageA.locator(`text=${PRIVATE_TODO_TITLE}`)).toBeVisible({
      timeout: 10_000,
    });

    console.log(`✅ User A (${emailA}) created: "${PRIVATE_TODO_TITLE}"`);
    await contextA.close();

    // ── User B Session ──────────────────────────────────────────────────────
    // Use a completely separate browser context (separate cookies / localStorage)
    const contextB = await browser.newContext();
    const pageB = await registerAndLogin(contextB, emailB, PASSWORD);

    // User B should see their own empty todo list
    await expect(pageB.locator(`text=${PRIVATE_TODO_TITLE}`)).not.toBeVisible({
      timeout: 10_000,
    });

    console.log(
      `✅ User B (${emailB}) does NOT see User A's private todo – isolation confirmed`
    );
    await contextB.close();
  });

  test("User B cannot access User A's todo via direct API call (backend check)", async ({
    request,
  }) => {
    /**
     * This test calls the API directly (bypassing the UI) to verify the
     * backend authorization boundary is enforced.
     *
     * Even if the UI filters correctly, the API must also reject unauthorized
     * access – otherwise a malicious client could bypass the UI.
     */
    const API_URL =
      process.env.API_URL || "http://localhost:8000/api/v1";

    const emailApiA = uniqueEmail("apiA");
    const emailApiB = uniqueEmail("apiB");

    // Register User A via API
    const regA = await request.post(`${API_URL}/auth/register`, {
      data: { email: emailApiA, password: PASSWORD },
    });
    expect(regA.ok()).toBeTruthy();
    const tokenA = (await regA.json()).access_token;

    // User A creates a todo
    const createResp = await request.post(`${API_URL}/todos`, {
      data: { title: "User A Private API Todo" },
      headers: { Authorization: `Bearer ${tokenA}` },
    });
    expect(createResp.status()).toBe(201);
    const todoId = (await createResp.json()).id;

    // Register User B via API
    const regB = await request.post(`${API_URL}/auth/register`, {
      data: { email: emailApiB, password: PASSWORD },
    });
    expect(regB.ok()).toBeTruthy();
    const tokenB = (await regB.json()).access_token;

    // User B tries to read User A's todo directly via API
    const getResp = await request.get(`${API_URL}/todos/${todoId}`, {
      headers: { Authorization: `Bearer ${tokenB}` },
    });

    expect([403, 404]).toContain(getResp.status());
    console.log(
      `✅ API returned ${getResp.status()} – User B cannot access User A's todo via direct API call`
    );

    // User B tries to update User A's todo
    const putResp = await request.put(`${API_URL}/todos/${todoId}`, {
      data: { title: "Hacked by User B" },
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    expect([403, 404]).toContain(putResp.status());

    // User B tries to delete User A's todo
    const delResp = await request.delete(`${API_URL}/todos/${todoId}`, {
      headers: { Authorization: `Bearer ${tokenB}` },
    });
    expect([403, 404]).toContain(delResp.status());

    console.log(
      `✅ All cross-user API operations (GET, PUT, DELETE) correctly blocked`
    );
  });
});
