// Snap de /memoria, /memoria/<id> y /buscar con Playwright + Chromium.
//
// Seedea localStorage["ynara.user"] (guard del route group (app)) y captura
// las 3 vistas del feature Memoria, mobile (390x844) y desktop (1280x800),
// con deviceScaleFactor=1 (DPR 2 produce PNGs >2000px que rompen el preview).
//
// El timeline y el detalle dependen del backend FastAPI; sin él en marcha,
// las vistas resuelven a los estados editoriales que igual queremos validar
// (skeleton -> empty/error, NotFound del detalle). /buscar arranca en el
// estado de sugerencias (sin query) sin necesidad de red.
//
// Uso: pnpm --filter @ynara/web exec node scripts/snap-memoria.mjs
//      (asume dev en SNAP_BASE_URL, default http://localhost:3000)

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const BASE = process.env.SNAP_BASE_URL ?? "http://localhost:3000";
const OUT = resolve(process.cwd(), ".shots");
mkdirSync(OUT, { recursive: true });

const NOW = 1717250000000;

const USER_SEED = JSON.stringify({
  state: {
    userId: "snap-user",
    token: "snap-token",
    displayName: "Mateo",
    isEphemeral: true,
    mood: ["tranquilo"],
    moodFreeText: "",
    interestedModes: ["productividad"],
    onboardingCompleted: true,
    onboardedAt: NOW,
  },
  version: 0,
});

const SHOTS = [
  { name: "memoria", path: "/memoria" },
  // Detalle: ref/capa válidos a nivel de schema; el backend responderá 404 y
  // caemos en el NotFound editorial, que es la pantalla terminal sobria.
  { name: "memoria-detalle", path: "/memoria/snap-ref?capa=semantic" },
  { name: "buscar", path: "/buscar" },
];

const VIEWPORTS = [
  { label: "mobile", width: 390, height: 844 },
  { label: "desktop", width: 1280, height: 800 },
];

const browser = await chromium.launch();
try {
  for (const shot of SHOTS) {
    for (const vp of VIEWPORTS) {
      const ctx = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 1,
      });
      const page = await ctx.newPage();
      await page.addInitScript((seed) => {
        localStorage.setItem("ynara.user", seed);
      }, USER_SEED);

      await page.goto(`${BASE}${shot.path}`, { waitUntil: "networkidle" });
      await page.addStyleTag({
        content: `
          nextjs-portal,
          #__next-build-watcher,
          [data-next-badge-root],
          [data-next-badge],
          [data-nextjs-toast] { display: none !important; }
        `,
      });
      await page.waitForTimeout(1500);

      const file = `${shot.name}-${vp.label}.png`;
      await page.screenshot({ path: resolve(OUT, file), fullPage: false });
      console.log(`✓ ${file}`);

      await ctx.close();
    }
  }
} finally {
  await browser.close();
}
