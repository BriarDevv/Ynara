// Snap de /chat con Playwright + Chromium.
//
// Seedea localStorage["ynara.user"] (guard de onboarding) +
// localStorage["ynara.chat"] (sesión + mensajes) y captura
// `/chat/<sessionId>` mobile y desktop, tanto con conversación
// como en estado vacío.
//
// Uso: pnpm --filter @ynara/web exec node scripts/snap-chat.mjs

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const BASE = process.env.SNAP_BASE_URL ?? "http://localhost:3000";
const OUT = resolve(process.cwd(), ".shots");
mkdirSync(OUT, { recursive: true });

const SESSION_ID_FULL = "snap-session-full";
const SESSION_ID_EMPTY = "snap-session-empty";
const NOW = 1717250000000;

const USER_SEED = JSON.stringify({
  state: {
    userId: "snap-user",
    token: "snap-token",
    displayName: "Mateo",
    mood: ["tranquilo"],
    moodFreeText: "",
    interestedModes: ["productividad"],
    onboardingCompleted: true,
    onboardedAt: NOW,
  },
  version: 0,
});

const CHAT_SEED = JSON.stringify({
  state: {
    sessions: {
      [SESSION_ID_FULL]: {
        id: SESSION_ID_FULL,
        mode: "productividad",
        createdAt: NOW,
        updatedAt: NOW,
      },
      [SESSION_ID_EMPTY]: {
        id: SESSION_ID_EMPTY,
        mode: "bienestar",
        createdAt: NOW,
        updatedAt: NOW,
      },
    },
    messages: {
      [SESSION_ID_FULL]: [
        {
          id: "u1",
          role: "user",
          text: "Necesito ordenarme la semana, tengo 3 entregas y una reunión floja.",
          status: "done",
        },
        {
          id: "a1",
          role: "assistant",
          text: "Dale, empecemos por la entrega más cercana. ¿Cuál tiene la fecha más próxima y qué te falta para cerrarla?",
          status: "done",
        },
        {
          id: "u2",
          role: "user",
          text: "El informe para el viernes — me falta revisar los datos del Q2.",
          status: "done",
        },
        {
          id: "a2",
          role: "assistant",
          text: "Bien. Te propongo un bloque mañana de 9 a 11 para Q2, sin interrupciones. ¿Te sirve, o preferís tarde?",
          status: "done",
        },
      ],
      [SESSION_ID_EMPTY]: [],
    },
  },
  version: 0,
});

const SHOTS = [
  { name: "chat-full", path: `/chat/${SESSION_ID_FULL}` },
  { name: "chat-empty", path: `/chat/${SESSION_ID_EMPTY}` },
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
      await page.addInitScript(
        ({ user, chat }) => {
          localStorage.setItem("ynara.user", user);
          localStorage.setItem("ynara.chat", chat);
        },
        { user: USER_SEED, chat: CHAT_SEED },
      );

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
      await page.waitForTimeout(1200);

      const file = `${shot.name}-${vp.label}.png`;
      await page.screenshot({ path: resolve(OUT, file), fullPage: false });
      console.log(`✓ ${file}`);
      await ctx.close();
    }
  }
} finally {
  await browser.close();
}
