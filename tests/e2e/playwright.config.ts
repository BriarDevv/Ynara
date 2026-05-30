import { defineConfig, devices } from "@playwright/test";

/**
 * Config e2e de Ynara web (plan Sesión 6 §2).
 *
 * - `webServer` levanta el dev de apps/web con MSW activo
 *   (`NEXT_PUBLIC_ENABLE_MOCKS=true`), de modo que /v1/auth/* y
 *   /v1/user/onboard respondan con los handlers de `src/lib/api.mocks.ts`
 *   sin necesitar el backend real (regla AGENTS: nada sale del perímetro).
 * - El `predev` de apps/web corre `msw init public/`, generando el
 *   service worker que MSW usa en el browser.
 * - Un solo project chromium: el e2e valida el flujo, no cross-browser.
 *
 * Pre-requisitos para correrlo localmente:
 *   1. `pnpm exec playwright install chromium`  (descarga el browser)
 *   2. `pnpm exec playwright test --config tests/e2e/playwright.config.ts`
 *      (o `cd tests/e2e && pnpm exec playwright test`)
 */
export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: "http://localhost:3100",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // Corremos el dev de apps/web desde el root del monorepo via pnpm filter.
    // Regeneramos el worker MSW (idempotente) antes de arrancar para no
    // depender del `predev`, que `next dev --port` directo no dispara.
    // Puerto 3100 para no chocar con un `next dev` manual en 3000.
    command:
      "pnpm --filter @ynara/web exec msw init public/ --no-save && pnpm --filter @ynara/web exec next dev --port 3100",
    url: "http://localhost:3100",
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    env: {
      NEXT_PUBLIC_ENABLE_MOCKS: "true",
      NEXT_PUBLIC_API_URL: "http://localhost:8080",
    },
  },
});
