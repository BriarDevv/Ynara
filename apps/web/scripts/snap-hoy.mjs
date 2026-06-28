// Snap de /hoy con Playwright + Chromium.
//
// Seedea localStorage["ynara.user"] con onboardingCompleted=true para
// bypassear el guard del route group (app) (apps/web/src/app/(app)/layout.tsx).
// Captura mobile (390x844) y desktop (1280x800, fullPage).
//
// Uso: pnpm --filter @ynara/web exec node scripts/snap-hoy.mjs
//      (asume dev en SNAP_BASE_URL, default http://localhost:3000)

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const BASE = process.env.SNAP_BASE_URL ?? "http://localhost:3000";
const OUT = resolve(process.cwd(), ".shots");
mkdirSync(OUT, { recursive: true });

/**
 * Estado mínimo del useUserStore persistido (zustand persist) para que
 * el guard de (app)/layout.tsx deje pasar.
 */
const USER_SEED = JSON.stringify({
  state: {
    userId: "snap-user",
    token: "snap-token",
    displayName: "Mateo",
    mood: ["tranquilo"],
    moodFreeText: "",
    interestedModes: ["productividad"],
    onboardingCompleted: true,
    onboardedAt: Date.now(),
  },
  version: 0,
});

const VIEWPORTS = [
  { label: "mobile", width: 390, height: 844 },
  { label: "desktop", width: 1280, height: 800 },
];

const browser = await chromium.launch();
try {
  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    await page.addInitScript((seed) => {
      localStorage.setItem("ynara.user", seed);
    }, USER_SEED);

    await page.goto(`${BASE}/hoy`, { waitUntil: "networkidle" });
    await page.addStyleTag({
      content: `
        nextjs-portal,
        #__next-build-watcher,
        [data-next-badge-root],
        [data-next-badge],
        [data-nextjs-toast] { display: none !important; }
      `,
    });
    await page.waitForTimeout(1800);

    const file = `hoy-${vp.label}.png`;
    await page.screenshot({ path: resolve(OUT, file), fullPage: true });
    console.log(`✓ ${file}`);

    await ctx.close();
  }
} finally {
  await browser.close();
}
