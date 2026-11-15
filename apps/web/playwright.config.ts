import { defineConfig, devices } from "@playwright/test";

const isLive = process.env.E2E_LIVE === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: isLive ? (process.env.E2E_BASE_URL || "http://127.0.0.1:7860") : "http://127.0.0.1:3000",
    trace: "on-first-retry",
    ...(!isLive
      ? {
          storageState: {
            cookies: [
              {
                name: "NEXT_PUBLIC_MOCK",
                value: "1",
                domain: "127.0.0.1",
                path: "/",
                expires: -1,
                httpOnly: false,
                secure: false,
                sameSite: "Lax" as const,
              },
            ],
            origins: [],
          },
        }
      : {}),
  },
  ...(isLive
    ? {}
    : {
        webServer: {
          command: "npm run start",
          url: "http://127.0.0.1:3000",
          reuseExistingServer: !process.env.CI,
          timeout: 120 * 1000,
          env: {
            NEXT_PUBLIC_MOCK: "1",
            MOCK: "1",
            PORT: "3000",
          },
        },
      }),
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
