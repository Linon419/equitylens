import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "cd ../backend && uv run uvicorn tests.e2e_app:app --host 127.0.0.1 --port 8001",
      url: "http://127.0.0.1:8001/api/v1/health/live",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command:
        "BACKEND_URL=http://127.0.0.1:8001 FRONTEND_URL=http://127.0.0.1:3000 NEXT_PUBLIC_GOOGLE_CLIENT_ID=e2e-client COOKIE_SECURE=false corepack pnpm dev --hostname 127.0.0.1",
      url: "http://127.0.0.1:3000/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
