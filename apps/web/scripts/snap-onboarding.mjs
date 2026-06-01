// Snapshot del onboarding con Playwright + Chromium.
//
// Uso:
//   pnpm --filter @ynara/web exec node scripts/snap-onboarding.mjs
//   (asume `pnpm --filter @ynara/web dev` corriendo en http://localhost:3001)
//
// Genera capturas mobile (390x844) y desktop (1280x800) de cada step
// del onboarding. Para steps internos (`nombre`, `dia`, `modos`, `a11y`)
// hace seed del sessionStorage del store de onboarding antes del `goto`
// para bypassear el guard URL-jump del StepRouter.

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const BASE = process.env.SNAP_BASE_URL ?? "http://localhost:3001";
const OUT = resolve(process.cwd(), ".shots");
mkdirSync(OUT, { recursive: true });

/** Steps a fotografiar. `seed` define el state del store antes de cargar. */
const STEPS = [
  { name: "01-auth-signup", path: "/onboarding/auth", seed: makeSeed("auth") },
  { name: "02-nombre", path: "/onboarding/nombre", seed: makeSeed("nombre") },
  { name: "03-dia", path: "/onboarding/dia", seed: makeSeed("dia") },
  { name: "04-modos", path: "/onboarding/modos", seed: makeSeed("modos") },
  { name: "05-a11y", path: "/onboarding/a11y", seed: makeSeed("a11y") },
];

const VIEWPORTS = [
  { label: "mobile", width: 390, height: 844 },
  { label: "desktop", width: 1280, height: 800 },
];

/**
 * Estado mínimo del store zustand-persist para que `currentStep`
 * coincida con la URL pedida y el StepRouter no redirija. Para steps
 * después de `auth`, finge auth completada (ephemeral).
 */
function makeSeed(currentStep) {
  const baseState = {
    currentStep,
    authedUserId: currentStep === "auth" ? null : "snap-user",
    authedToken: currentStep === "auth" ? null : "snap-token",
    authMode: currentStep === "auth" ? null : "ephemeral",
    displayName: "",
    mood: [],
    moodFreeText: "",
    interestedModes: [],
    a11yTextSize: "md",
    a11yHighContrast: false,
    a11yMotion: "auto",
  };
  return JSON.stringify({ state: baseState, version: 0 });
}

const browser = await chromium.launch();
try {
  for (const step of STEPS) {
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 2,
      });
      const page = await context.newPage();

      // Seed del sessionStorage antes del goto. addInitScript corre en
      // cada document load — perfecto para zustand-persist con
      // createJSONStorage(sessionStorage).
      await page.addInitScript((seed) => {
        sessionStorage.setItem("ynara.onboarding", seed);
      }, step.seed);

      await page.goto(`${BASE}${step.path}`, { waitUntil: "networkidle" });

      // Ocultar el dev-indicator de Next.js (la "N" turbo abajo a la
      // izquierda) para que no aparezca en las capturas. Sólo lo agregamos
      // post-load porque addStyleTag necesita un document.
      await page.addStyleTag({
        content: `
          nextjs-portal,
          #__next-build-watcher,
          [data-next-badge-root],
          [data-next-badge],
          [data-nextjs-toast] {
            display: none !important;
          }
        `,
      });

      // Esperar a que las animaciones de entrada terminen.
      await page.waitForTimeout(1800);

      const file = `${step.name}-${vp.label}.png`;
      /*
       * fullPage en desktop para capturar steps con muchas opciones
       * (Modes, Mood) que superan el viewport de 800px. En mobile
       * dejamos fullPage también: los steps caben en el viewport
       * de 844px pero scroll es real en mobile, queremos verlo todo.
       */
      await page.screenshot({ path: resolve(OUT, file), fullPage: true });
      console.log(`✓ ${file}`);

      await context.close();
    }
  }
} finally {
  await browser.close();
}
