import { expect, type Page, test } from "@playwright/test";
import { gatedViolations } from "./axe-utils";

/**
 * E2E del onboarding completo de Ynara web (plan Sesión 6 §2).
 *
 * Corre contra el dev de apps/web con MSW activo (ver playwright.config.ts):
 * los endpoints /v1/auth/signup y /v1/user/onboard responden con los
 * handlers de `src/lib/api.mocks.ts`, así no necesitamos el backend real.
 *
 * Cobertura:
 *   (a) happy path: auth(signup) → nombre → día → modos → a11y → outro → /hoy
 *   (b) error inline en auth (email inválido, validación cliente)
 *   (c) axe sin violations CRÍTICAS en /onboarding/auth y /hoy
 *
 * Nota sobre axe (plan §2 / PR #11): el gate son violations de impacto
 * `critical` MÁS las de `color-contrast` de impacto `serious`. Tras el QA de
 * contraste (PR #11) el texto "soft"/placeholder ya pasa AA, así que las
 * regresiones de contraste vuelven a gatear. El resto de las `serious`
 * (no-contraste) siguen fuera del gate por ahora.
 */

const STEP_TITLES = {
  auth: "Antes que nada",
  nombre: "¿Cómo te llamo?",
  dia: "¿Cómo viene tu día, en general?",
  modos: "¿Para qué te puedo servir?",
  a11y: "Ajustemos cómo se lee.",
} as const;

/** Recorre signup + nombre + día + modos + a11y hasta llegar al /hoy. */
async function completeOnboarding(page: Page): Promise<void> {
  await page.goto("/onboarding/auth");

  // --- Step 1: Auth (signup) ---
  await expect(page.getByRole("heading", { name: STEP_TITLES.auth })).toBeVisible();
  await page.getByLabel("EMAIL").fill("vos@ejemplo.com");
  await page.getByLabel("CONTRASEÑA").fill("supersecreta1");
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  // --- Step 2: Nombre — esperamos el heading antes de seguir, así el
  // locator "Seguir" no pega al botón del step anterior ---
  await expect(page.getByRole("heading", { name: STEP_TITLES.nombre })).toBeVisible();
  await page.getByLabel("TU NOMBRE").fill("Mateo");
  await page.getByRole("button", { name: "Seguir" }).click();

  // --- Step 3: Día (mood) — opcional, lo pasamos sin elegir ---
  await expect(page.getByRole("heading", { name: STEP_TITLES.dia })).toBeVisible();
  await page.getByRole("button", { name: "Seguir" }).click();

  // --- Step 4: Modos — productividad viene pre-marcado ---
  await expect(page.getByRole("heading", { name: STEP_TITLES.modos })).toBeVisible();
  await page.getByRole("button", { name: "Seguir" }).click();

  // --- Step 5: A11y — el CTA "Listo" dispara el outro de celebración ---
  await expect(page.getByRole("heading", { name: STEP_TITLES.a11y })).toBeVisible();
  await page.getByRole("button", { name: "Listo" }).click();

  // --- Outro → /hoy?welcome=true ---
  await page.waitForURL(/\/hoy/, { timeout: 20_000 });
}

test.describe("Onboarding", () => {
  test("happy path: recorre todos los steps y aterriza en /hoy", async ({ page }) => {
    await completeOnboarding(page);

    await expect(page).toHaveURL(/\/hoy/);
    // El home saluda con el nombre cargado durante el onboarding.
    await expect(page.getByText("Mateo")).toBeVisible();
  });

  test("auth muestra error inline con un email inválido", async ({ page }) => {
    await page.goto("/onboarding/auth");
    await expect(page.getByRole("heading", { name: STEP_TITLES.auth })).toBeVisible();

    await page.getByLabel("EMAIL").fill("no-es-un-email");
    await page.getByLabel("CONTRASEÑA").fill("supersecreta1");
    await page.getByRole("button", { name: "Crear cuenta" }).click();

    // La validación cliente (zodResolver) muestra el error sin navegar.
    await expect(page.getByText("Email inválido")).toBeVisible();
    await expect(page).toHaveURL(/\/onboarding\/auth/);
  });

  test("no tiene violations críticas de a11y en /onboarding/auth", async ({ page }) => {
    await page.goto("/onboarding/auth");
    await expect(page.getByRole("heading", { name: STEP_TITLES.auth })).toBeVisible();

    const violations = await gatedViolations(page);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });

  test("no tiene violations críticas de a11y en /hoy", async ({ page }) => {
    await completeOnboarding(page);
    await expect(page).toHaveURL(/\/hoy/);

    const violations = await gatedViolations(page);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });
});
