// Snap del logo en aislamiento — captura el YnaraMark del header del
// onboarding y de la pantalla de Celebration (mark grande con pulse).
//
// Uso: pnpm --filter @ynara/web exec node scripts/snap-logo.mjs
// Asume dev en SNAP_BASE_URL (default http://localhost:3000).

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

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
  await page.goto(`${BASE}/onboarding/auth`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);

  // YnaraMark del header — único SVG inline con role=img + aria-label=Ynara
  const mark = page.locator('svg[role="img"][aria-label="Ynara"]').first();
  await mark.waitFor({ state: "visible" });
  await mark.screenshot({
    path: resolve(OUT, "logo-header.png"),
    omitBackground: true,
  });
  console.log("✓ logo-header.png");

  // Mark grande de Outro — render inline en standalone HTML
  // para verificar el SVG en tamaño grande sin necesidad del flow.
  await page.setContent(
    `<!doctype html>
     <html>
       <body style="background:#FAF9F5; display:flex; gap:48px; padding:48px; align-items:center;">
         <iframe src="${BASE}/onboarding/auth" style="display:none"></iframe>
       </body>
     </html>`,
    { waitUntil: "domcontentloaded" },
  );

  // Render el SVG directamente para snap en tamaño grande
  await page.setContent(
    `<!doctype html>
     <html><head><style>
       body { background:#FAF9F5; margin:0; padding:48px; font-family:system-ui;
              display:flex; flex-direction:column; gap:48px; align-items:flex-start; }
       .row { display:flex; gap:32px; align-items:flex-end; }
       .label { font-size:11px; color:#5a6178; text-transform:uppercase; letter-spacing:.06em; margin-top:8px; }
     </style></head><body>
       <h1 style="font-family:'Space Grotesk',system-ui;font-size:24px;color:#1b2233;margin:0">YnaraMark — tamaños</h1>
       <div class="row">
         <div><svg viewBox="0 0 800 700" width="32" height="32" role="img" aria-label="Ynara"><defs>
           <linearGradient id="b" x1="240" y1="590" x2="560" y2="160" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#2F5AA6"/><stop offset="1" stop-color="#1F66DB"/></linearGradient>
           <linearGradient id="r" x1="330" y1="580" x2="470" y2="185" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#4B7EE6" stop-opacity=".88"/><stop offset="1" stop-color="#7BA1F4" stop-opacity=".55"/></linearGradient>
           <linearGradient id="d" x1="400" y1="48" x2="400" y2="168" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#8C63B8"/><stop offset="1" stop-color="#7C4FA3"/></linearGradient>
         </defs>
         <path d="M352 590 C352 590 352 470 352 427 C352 375 324 318 257 212 C241 188 218 173 192 181 C167 188 156 211 168 233 C221 335 269 413 302 485 C320 523 329 557 329 590 L471 590 C471 557 480 523 498 485 C531 413 579 335 632 233 C644 211 633 188 608 181 C582 173 559 188 543 212 C476 318 448 375 448 427 C448 470 448 590 448 590 Z" fill="url(#b)"/>
         <path d="M403 590 C403 541 394 498 378 457 C348 385 312 320 255 227 C247 213 238 201 233 192 C252 186 269 194 281 213 C343 311 379 372 399 422 C419 372 455 311 517 213 C529 194 546 186 565 192 C560 201 551 213 543 227 C486 320 450 385 420 457 C404 498 395 541 395 590 Z" fill="url(#r)"/>
         <path d="M400 48 L464 112 L400 176 L336 112 Z" fill="url(#d)"/>
         </svg><div class="label">32 (header mobile)</div></div>
         <div><svg viewBox="0 0 800 700" width="64" height="64" role="img"><use href="#" /></svg><div class="label"></div></div>
       </div>
       <div class="row">
         <div><svg viewBox="0 0 800 700" width="112" height="112" role="img" aria-label="Ynara"><defs>
           <linearGradient id="b2" x1="240" y1="590" x2="560" y2="160" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#2F5AA6"/><stop offset="1" stop-color="#1F66DB"/></linearGradient>
           <linearGradient id="r2" x1="330" y1="580" x2="470" y2="185" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#4B7EE6" stop-opacity=".88"/><stop offset="1" stop-color="#7BA1F4" stop-opacity=".55"/></linearGradient>
           <linearGradient id="d2" x1="400" y1="48" x2="400" y2="168" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#8C63B8"/><stop offset="1" stop-color="#7C4FA3"/></linearGradient>
         </defs>
         <path d="M352 590 C352 590 352 470 352 427 C352 375 324 318 257 212 C241 188 218 173 192 181 C167 188 156 211 168 233 C221 335 269 413 302 485 C320 523 329 557 329 590 L471 590 C471 557 480 523 498 485 C531 413 579 335 632 233 C644 211 633 188 608 181 C582 173 559 188 543 212 C476 318 448 375 448 427 C448 470 448 590 448 590 Z" fill="url(#b2)"/>
         <path d="M403 590 C403 541 394 498 378 457 C348 385 312 320 255 227 C247 213 238 201 233 192 C252 186 269 194 281 213 C343 311 379 372 399 422 C419 372 455 311 517 213 C529 194 546 186 565 192 C560 201 551 213 543 227 C486 320 450 385 420 457 C404 498 395 541 395 590 Z" fill="url(#r2)"/>
         <path d="M400 48 L464 112 L400 176 L336 112 Z" fill="url(#d2)"/>
         </svg><div class="label">112 (Outro)</div></div>
         <div><svg viewBox="0 0 800 700" width="256" height="256" role="img" aria-label="Ynara"><defs>
           <linearGradient id="b3" x1="240" y1="590" x2="560" y2="160" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#2F5AA6"/><stop offset="1" stop-color="#1F66DB"/></linearGradient>
           <linearGradient id="r3" x1="330" y1="580" x2="470" y2="185" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#4B7EE6" stop-opacity=".88"/><stop offset="1" stop-color="#7BA1F4" stop-opacity=".55"/></linearGradient>
           <linearGradient id="d3" x1="400" y1="48" x2="400" y2="168" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#8C63B8"/><stop offset="1" stop-color="#7C4FA3"/></linearGradient>
         </defs>
         <path d="M352 590 C352 590 352 470 352 427 C352 375 324 318 257 212 C241 188 218 173 192 181 C167 188 156 211 168 233 C221 335 269 413 302 485 C320 523 329 557 329 590 L471 590 C471 557 480 523 498 485 C531 413 579 335 632 233 C644 211 633 188 608 181 C582 173 559 188 543 212 C476 318 448 375 448 427 C448 470 448 590 448 590 Z" fill="url(#b3)"/>
         <path d="M403 590 C403 541 394 498 378 457 C348 385 312 320 255 227 C247 213 238 201 233 192 C252 186 269 194 281 213 C343 311 379 372 399 422 C419 372 455 311 517 213 C529 194 546 186 565 192 C560 201 551 213 543 227 C486 320 450 385 420 457 C404 498 395 541 395 590 Z" fill="url(#r3)"/>
         <path d="M400 48 L464 112 L400 176 L336 112 Z" fill="url(#d3)"/>
         </svg><div class="label">256 (inspección)</div></div>
       </div>
     </body></html>`,
    { waitUntil: "domcontentloaded" },
  );
  await page.waitForTimeout(300);
  await page.screenshot({ path: resolve(OUT, "logo-ladder.png"), fullPage: true });
  console.log("✓ logo-ladder.png");

  await ctx.close();
} finally {
  await browser.close();
}
