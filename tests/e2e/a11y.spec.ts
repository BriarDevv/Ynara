import { expect, type Page, test } from "@playwright/test";
import { gatedViolations } from "./axe-utils";

/**
 * Cobertura de accesibilidad de las vistas autenticadas (PR #11 — DESIGN.md
 * §16 #11). Corre axe (wcag2a/wcag2aa) sobre /memoria, /buscar y /hoy en claro
 * y en Noche, con el mismo criterio de fallo que onboarding.spec
 * (`isGatedViolation`): violations `critical` + `color-contrast` `serious`.
 *
 * Patrón de entrada SIN el onboarding (roto en main, issue #180): sembramos
 * `ynara.user` (onboarding completo) en localStorage ANTES del goto, igual que
 * smooth-scroll.spec / screen-transition.spec. Para las vistas en Noche
 * sembramos además `ynara.theme` (ver theme.spec).
 *
 * Corre contra el dev de apps/web con MSW activo (ver playwright.config.ts).
 *
 * FOLLOW-UP (no cubierto acá): /chat — requiere sembrar el store de sesión del
 * chat (costoso de armar a mano), queda pendiente para un spec aparte.
 */

/** Formato de zustand/persist para la key ynara.user (version 0 por defecto). */
const ONBOARDED = JSON.stringify({
  state: { onboardingCompleted: true, displayName: "Mateo" },
  version: 0,
});

/** Formato de zustand/persist para la key ynara.theme en Noche. */
const DARK_PERSISTED = JSON.stringify({ state: { theme: "dark" }, version: 0 });

/** Siembra el estado de usuario (onboarding completo) ANTES de cargar el doc. */
async function seedOnboarded(page: Page): Promise<void> {
  await page.addInitScript((value) => {
    localStorage.setItem("ynara.user", value);
  }, ONBOARDED);
}

/** Siembra el tema Noche ANTES de cargar el doc (pre-paint, sin FOUC). */
async function seedDark(page: Page): Promise<void> {
  await page.addInitScript((value) => {
    localStorage.setItem("ynara.theme", value);
  }, DARK_PERSISTED);
}

test.describe("a11y de vistas autenticadas", () => {
  test("/memoria en claro no tiene violations que gateen", async ({ page }) => {
    await seedOnboarded(page);
    await page.goto("/memoria");
    await expect(page.getByRole("heading", { level: 1, name: "Memoria" })).toBeVisible();

    const violations = await gatedViolations(page);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });

  test("/buscar en claro no tiene violations que gateen", async ({ page }) => {
    await seedOnboarded(page);
    await page.goto("/buscar");
    await expect(page.getByRole("heading", { level: 1, name: "Buscar" })).toBeVisible();

    const violations = await gatedViolations(page);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });

  test("/hoy en Noche no tiene violations que gateen", async ({ page }) => {
    await seedOnboarded(page);
    await seedDark(page);
    await page.goto("/hoy");
    await expect(page.getByRole("heading", { level: 1, name: "Hoy" })).toBeVisible();
    // Confirmamos que el tema Noche está efectivamente aplicado antes de medir.
    await expect(page.locator("html")).toHaveClass(/theme-dark/);

    const violations = await gatedViolations(page);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });

  test("/memoria en Noche no tiene violations que gateen", async ({ page }) => {
    await seedOnboarded(page);
    await seedDark(page);
    await page.goto("/memoria");
    await expect(page.getByRole("heading", { level: 1, name: "Memoria" })).toBeVisible();
    await expect(page.locator("html")).toHaveClass(/theme-dark/);

    const violations = await gatedViolations(page);
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });

  test("el LivingField queda fuera del árbol de accesibilidad", async ({ page }) => {
    await seedOnboarded(page);
    await page.goto("/hoy");
    await expect(page.getByRole("heading", { level: 1, name: "Hoy" })).toBeVisible();

    // /hoy monta el fondo vivo (LivingField variant="aurora", HoyView): el
    // canvas existe en el DOM. Esperamos a que aparezca antes de medir.
    await expect(page.locator("canvas").first()).toBeAttached();

    // El canvas es decoración pura (§2.3): vive dentro de un wrapper
    // aria-hidden, así que jamás compite con el contenido ni se expone como
    // elemento accesible. Afirmamos que TODO canvas está bajo un
    // [aria-hidden="true"] (mismo invariante que living-field.spec).
    const allCanvasHidden = await page.evaluate(() => {
      const canvases = Array.from(document.querySelectorAll("canvas"));
      return (
        canvases.length > 0 && canvases.every((c) => c.closest('[aria-hidden="true"]') !== null)
      );
    });
    expect(allCanvasHidden).toBe(true);
  });
});
