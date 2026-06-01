// E2E click-through del onboarding completo, sin seed del store.
//
// Uso: pnpm --filter @ynara/web exec node scripts/flow-onboarding.mjs
// Verifica:
//   1. /onboarding/auth → "Probar sin cuenta" → /onboarding/nombre
//   2. tipear nombre → "Seguir" → /onboarding/dia
//   3. tildear 1 mood → "Seguir" → /onboarding/modos
//   4. tildear 1 modo extra → "Seguir" → /onboarding/a11y
//   5. clickear "Listo" → CelebrationOutro → redirect a "/"
//
// Captura screenshot al final de cada paso para que sirva de evidencia.

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const BASE = process.env.SNAP_BASE_URL ?? "http://localhost:3000";
const OUT = resolve(process.cwd(), ".shots/flow");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  deviceScaleFactor: 2,
});
const page = await ctx.newPage();

// Helper para log de pasos y captura
let n = 0;
async function snap(label) {
  n += 1;
  const name = `${String(n).padStart(2, "0")}-${label}.png`;
  await page.screenshot({ path: resolve(OUT, name), fullPage: true });
  console.log(`✓ ${name}  url=${page.url()}`);
}

function assertUrl(expected) {
  const u = new URL(page.url());
  if (u.pathname !== expected) {
    throw new Error(`URL mismatch: expected ${expected}, got ${u.pathname}`);
  }
}

try {
  console.log(`[flow] BASE=${BASE}`);

  // 1) Auth
  await page.goto(`${BASE}/onboarding/auth`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  assertUrl("/onboarding/auth");
  await snap("auth");

  // "Probar sin cuenta" → arranca ephemeral, next()
  await page.getByRole("button", { name: /probar sin cuenta/i }).click();
  await page.waitForURL(`${BASE}/onboarding/nombre`, { timeout: 5000 });
  assertUrl("/onboarding/nombre");
  await page.waitForTimeout(500);
  await snap("nombre-empty");

  // 2) Nombre
  await page.getByLabel(/tu nombre/i).fill("Mateo");
  await page.getByRole("button", { name: /^seguir$/i }).click();
  await page.waitForURL(`${BASE}/onboarding/dia`, { timeout: 5000 });
  assertUrl("/onboarding/dia");
  await page.waitForTimeout(500);
  await snap("dia");

  // 3) Mood — tildear "Tranquilo, con tiempo" (primer option card)
  await page.getByRole("button", { name: /tranquilo, con tiempo/i }).click();
  await page.getByRole("button", { name: /^seguir$/i }).click();
  await page.waitForURL(`${BASE}/onboarding/modos`, { timeout: 5000 });
  assertUrl("/onboarding/modos");
  await page.waitForTimeout(500);
  await snap("modos");

  // 4) Modos — Productividad ya viene pre-seleccionado por DEFAULT_MODE.
  // Solo "Seguir".
  await page.getByRole("button", { name: /^seguir$/i }).click();
  await page.waitForURL(`${BASE}/onboarding/a11y`, { timeout: 5000 });
  assertUrl("/onboarding/a11y");
  await page.waitForTimeout(500);
  await snap("a11y");

  // 5) A11y — click "Listo"; el outro corre 1500ms y redirige.
  await page.getByRole("button", { name: /^listo$/i }).click();
  // Esperar el CelebrationOutro: la URL todavía es /onboarding/a11y
  // pero el render cambia. Snap durante el outro.
  await page.waitForTimeout(800);
  await snap("outro");

  // Después de 1500ms desde Listo, useCompleteOnboarding navega a "/".
  await page.waitForURL((u) => u.pathname === "/", { timeout: 5000 });
  await page.waitForTimeout(500);
  await snap("post-onboarding-home");
  assertUrl("/");

  console.log("[flow] DONE — onboarding completo OK");
} catch (err) {
  console.error("[flow] FAIL", err.message);
  await snap("error");
  process.exitCode = 1;
} finally {
  await ctx.close();
  await browser.close();
}
