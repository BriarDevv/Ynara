// Snap del logo en aislamiento — captura el lockup del header del onboarding
// y la galería de marca de /test-ds (variantes del símbolo + YnaraWordmark),
// en claro y en Noche.
//
// Uso: pnpm --filter @ynara/web exec node scripts/snap-logo.mjs
// Asume dev en SNAP_BASE_URL (default http://localhost:3000).
//
// Captura los COMPONENTES REALES (no SVG hardcodeado): así el snapshot nunca
// se desincroniza de YnaraMark/YnaraWordmark. La galería se ancla con el
// atributo `data-logo-gallery` de la sección Marca del sandbox.

import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "@playwright/test";

const BASE = process.env.SNAP_BASE_URL ?? "http://localhost:3000";
const OUT = resolve(process.cwd(), ".shots");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 3,
  });
  const page = await ctx.newPage();

  // 1) Lockup del header del onboarding (uso real, in situ).
  await page.goto(`${BASE}/onboarding/auth`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const headerMark = page.locator('svg[role="img"][aria-label="Ynara"]').first();
  await headerMark.waitFor({ state: "visible" });
  await headerMark.screenshot({ path: resolve(OUT, "logo-header.png"), omitBackground: true });
  console.log("✓ logo-header.png");

  // 2) Galería de marca del sandbox: variantes del símbolo + wordmark.
  await page.goto(`${BASE}/test-ds`, { waitUntil: "networkidle" });
  const gallery = page.locator("[data-logo-gallery]");
  await gallery.waitFor({ state: "visible" });
  // Esperar a que la fuente display cargue (el wordmark usa <text>).
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);

  await gallery.screenshot({ path: resolve(OUT, "logo-gallery.png") });
  console.log("✓ logo-gallery.png (claro)");

  // 3) Misma galería en Noche (togglear el tema del sandbox).
  await page.getByRole("button", { name: "Cambiar tema" }).click();
  await page.waitForFunction(() => document.documentElement.classList.contains("theme-dark"));
  await page.waitForTimeout(300);
  await gallery.screenshot({ path: resolve(OUT, "logo-gallery-dark.png") });
  console.log("✓ logo-gallery-dark.png (Noche)");

  await ctx.close();
} finally {
  await browser.close();
}
