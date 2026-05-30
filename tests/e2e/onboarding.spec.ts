import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

/**
 * E2E del onboarding completo de Ynara web (plan Sesión 6 §2).
 *
 * Corre contra el dev de apps/web con MSW activo (ver playwright.config.ts):
 * los endpoints /v1/auth/signup y /v1/user/onboard responden con los
 * handlers de `src/lib/api.mocks.ts`, así no necesitamos el backend real.
 *
 * Cobertura:
 *   (a) happy path: auth(signup) → nombre → día → modos → a11y → outro → /home
 *   (b) error inline en auth (email inválido, validación cliente)
 *   (c) axe sin violations CRÍTICAS en /onboarding/auth y /home
 *
 * Nota sobre axe (plan §2): el gate son violations de impacto `critical`.
 * Las páginas hoy tienen violations `serious` de `color-contrast` (tokens
 * del DS con contraste por debajo de AA en textos "soft"/placeholder); eso
 * es un tema de diseño abierto, no se gatea acá. Si querés endurecer el
 * gate a `serious`, sumá "serious" a IMPACTS_TO_FAIL una vez resuelto el DS.
 */

const STEP_TITLES = {
  auth: "Antes que nada",
  nombre: "¿Cómo te llamo?",
  dia: "¿Cómo viene tu día, en general?",
  modos: "¿Para qué te puedo servir?",
  a11y: "Ajustemos cómo se lee.",
} as const;

const IMPACTS_TO_FAIL = new Set(["critical"]);

/** Recorre signup + nombre + día + modos + a11y hasta llegar al /home. */
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

  // --- Outro → /home?welcome=true ---
  await page.waitForURL(/\/home/, { timeout: 20_000 });
}

async function criticalViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.filter((v) => IMPACTS_TO_FAIL.has(v.impact ?? ""));
}

test.describe("Onboarding", () => {
  test("happy path: recorre todos los steps y aterriza en /home", async ({ page }) => {
    await completeOnboarding(page);

    await expect(page).toHaveURL(/\/home/);
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

    const critical = await criticalViolations(page);
    expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
  });

  test("no tiene violations críticas de a11y en /home", async ({ page }) => {
    await completeOnboarding(page);
    await expect(page).toHaveURL(/\/home/);

    const critical = await criticalViolations(page);
    expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
  });
});
