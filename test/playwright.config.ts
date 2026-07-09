import { defineConfig, devices } from '@playwright/test';

// Same-origin app: FastAPI serves both /api/* and the static frontend on 8000.
const baseURL = process.env.BASE_URL || 'http://localhost:8000';

export default defineConfig({
  testDir: './tests',
  // The backend is single-user global state (one portfolio, one watchlist), so
  // tests cannot run in parallel against it — they share one server.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  globalSetup: './global-setup.ts',
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'chromium',
      // Wide desktop viewport (>= lg breakpoint) so the chat panel is docked and
      // always visible, matching the desktop-first design in PLAN.md §10.
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        // The compose app is reached over plain HTTP at a single-label host
        // ("app"). Chromium's HTTPS-Upgrade feature rewrites that to https:// and
        // fails with ERR_SSL_PROTOCOL_ERROR (no fallback for single-label hosts),
        // so disable it for the test browser.
        launchOptions: {
          args: [
            '--disable-features=HttpsUpgrades,HttpsFirstBalancedModeAutoEnable,HttpsFirstModeV2ForTypicallySecureUsers',
          ],
        },
      },
    },
  ],
});
