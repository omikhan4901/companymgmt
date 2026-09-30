import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real API, a real Postgres, and the production static
 * build served with its real security headers (scripts/serve.mjs mirrors Cloudflare).
 * PW_CHROMIUM_PATH points at a preinstalled Chromium when the bundled one isn't available.
 */
const executablePath = process.env.PW_CHROMIUM_PATH || undefined;
const launchOptions = executablePath ? { executablePath } : {};
const WEB = "http://localhost:3000";
// The API only accepts /v1 through the web proxy, as in production (functions/v1).
const PROXY_TOKEN = "e2e-proxy-token";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: WEB,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "en-GB",
    timezoneId: "Asia/Dhaka",
    permissions: ["geolocation"],
    geolocation: { latitude: 23.7386, longitude: 90.3958, accuracy: 15 },
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
      env: { ENV: "dev", EMAIL_BACKEND: "console", CORS_ORIGINS: WEB, WEB_BASE_URL: WEB, PROXY_TOKEN },
    },
    {
      // The static export must exist (check.sh builds it first).
      command: `PORT=3000 API_ORIGIN=http://localhost:8000 PROXY_TOKEN=${PROXY_TOKEN} node scripts/serve.mjs`,
      url: `${WEB}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
