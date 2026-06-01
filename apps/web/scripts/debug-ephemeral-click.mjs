// Debug: ¿qué pasa cuando se clickea "Probar sin cuenta" en /onboarding/auth?
// Loguea sessionStorage, console del browser, y URL antes/después del click.

import { chromium } from "@playwright/test";

const BASE = process.env.SNAP_BASE_URL ?? "http://localhost:3000";

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();

page.on("console", (msg) => console.log(`[browser ${msg.type()}] ${msg.text()}`));
page.on("pageerror", (err) =>
  console.error(`[browser-error] ${err.name}: ${err.message}`),
);

console.log(`goto ${BASE}/onboarding/auth`);
await page.goto(`${BASE}/onboarding/auth`, { waitUntil: "networkidle" });

// Esperar más allá del hydration típico de zustand-persist.
await page.waitForTimeout(2000);

const before = await page.evaluate(() => ({
  url: window.location.pathname,
  storage: sessionStorage.getItem("ynara.onboarding"),
}));
console.log("--- BEFORE click ---");
console.log("URL:", before.url);
console.log("sessionStorage[ynara.onboarding]:", before.storage);

console.log('--- clicking "Probar sin cuenta" ---');
await page.getByRole("button", { name: /probar sin cuenta/i }).click();

// Esperar a que cualquier nav termine.
await page.waitForTimeout(2500);

const after = await page.evaluate(() => ({
  url: window.location.pathname,
  storage: sessionStorage.getItem("ynara.onboarding"),
}));
console.log("--- AFTER click + 2.5s ---");
console.log("URL:", after.url);
console.log("sessionStorage[ynara.onboarding]:", after.storage);

await ctx.close();
await browser.close();
