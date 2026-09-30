import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real API and a real Postgres.
 * Starts the API on :8000 and the web app on :5173 unless they're already running.
 * PW_CHROMIUM_PATH points at a preinstalled Chromium when the bundled one isn't available.
 */
const executablePath = process.env.PW_CHROMIUM_PATH || undefined;
const launchOptions = executablePath ? { executablePath } : {};

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "en-GB",
    timezoneId: "Asia/Dhaka",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], launchOptions } },
    { name: "phone", use: { ...devices["Pixel 7"], launchOptions } },
  ],
  webServer: [
    {
      command: "cd ../api && uv run alembic upgrade head && uv run uvicorn app.main:app --port 8000",
      url: "http://localhost:8000/healthz",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { ENV: "dev", EMAIL_BACKEND: "console", CORS_ORIGINS: "http://localhost:5173", WEB_BASE_URL: "http://localhost:5173" },
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
