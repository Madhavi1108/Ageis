import { defineConfig, devices } from "@playwright/test";

/*
 * Manual / non-blocking smoke test. NOT run in CI (see .github/workflows/ci.yml).
 *
 * Prerequisite: a real backend on :8000 started with the fake sandbox + mock AI
 * provider, e.g. from backend/:
 *   AEGIS_SANDBOX_MODE=fake AEGIS_AI_PROVIDER=mock uvicorn app.main:app --port 8000
 * This config's webServer starts the Vite dev server automatically.
 */
export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    port: 5173,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
