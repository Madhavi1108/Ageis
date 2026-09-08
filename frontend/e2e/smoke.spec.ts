import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Manual / non-blocking end-to-end smoke test. NOT run in CI.
 *
 * Prerequisite: a real AEGIS backend on http://localhost:8000 started with the
 * fake sandbox + mock AI provider, e.g. from backend/:
 *
 *   AEGIS_SANDBOX_MODE=fake AEGIS_AI_PROVIDER=mock uvicorn app.main:app --port 8000
 *
 * The Vite dev server is started automatically by playwright.config.ts.
 * Run with:  npm run e2e
 */

const LOCAL_REPO_PATH = process.env.AEGIS_E2E_REPO ?? "../test-repositories/aegis-acceptance";

test("create a repo + task, run the pipeline, inspect every stage", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/API (connected|checking)/)).toBeVisible();

  // point the dashboard at the backend
  await page.goto("/settings");
  await page.getByLabel(/API base URL override/i).fill("http://localhost:8000");
  await page.getByRole("button", { name: "Save" }).first().click();

  // register a repository + create a task
  await page.goto("/tasks/new");
  await page.getByLabel(/Local path/i).fill(LOCAL_REPO_PATH);
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page.getByText(/Registered/)).toBeVisible({ timeout: 15_000 });

  await page.getByLabel(/Issue \/ bug \/ feature text/i).fill(
    "calculate_total allows a discount above 0.5; cap it at 0.5",
  );
  await page.getByLabel(/Allowed paths/i).fill("invoice.py");
  await page.getByRole("button", { name: "Create task" }).click();

  // pipeline view
  await expect(page).toHaveURL(/\/tasks\/.+/);
  await expect(page.getByText("Verify")).toBeVisible();

  // poll to a terminal state
  await expect(async () => {
    const badge = page.locator("header ~ * >> text=/COMPLETED|PARTIALLY SUPPORTED|FAILED/").first();
    await expect(badge).toBeVisible();
  }).toPass({ timeout: 120_000 });

  // inspect a few stages
  await page.getByRole("button", { name: /Implement/ }).click();
  await page.getByRole("link", { name: /Open diff view/ }).click();
  await expect(page.getByText(/Raw patch|files? changed/i)).toBeVisible();

  await page.getByRole("link", { name: "Verification" }).click();
  await expect(page.getByText(/Verdict/)).toBeVisible();

  // knowledge graph renders (best-effort; needs an analysed snapshot)
  const a11y = await new AxeBuilder({ page }).analyze();
  // report-only: attach, don't fail the run
  test.info().annotations.push({
    type: "axe",
    description: `${a11y.violations.length} violations on the verification page`,
  });
});
