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

/** Siembra preferencias de a11y persistidas ANTES de cargar el doc. */
async function seedA11y(
  page: Page,
  state: { textSize?: string; highContrast?: boolean; motion?: string },
): Promise<void> {
  await page.addInitScript(
    (value) => {
      localStorage.setItem("ynara.a11y", value);
    },
    JSON.stringify({ state, version: 0 }),
  );
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

test.describe("pre-paint de a11y (#182)", () => {
  test("el script inline aplica las preferencias persistidas sin React (sin FOUC)", async ({
    page,
  }) => {
    await seedA11y(page, { textSize: "lg", highContrast: true, motion: "reduce" });

    // Abortar los chunks JS de Next ANTES de navegar: React nunca hidrata, así
    // que si las clases aparecen las puso el <script> inline del <head> (el
    // pre-paint real), no el A11yApplier post-hidratación. Mismo método que
    // theme.spec (pata a): sin el abort, el applier daría falso verde.
    //
    // El fix de #182 (A11yApplier con getState()+subscribe, espejo de
    // ThemeApplier) elimina la lectura del valor hidratado-stale y el re-render
    // redundante. Su correctitud descansa en ese patrón ya revisado, no en un
    // catcher del "stomp": en React 19 + zustand 5 el transitorio default→real se
    // coalesce en una sola tarea (sin paint intermedio), así que no es observable
    // por e2e —el bug es la lectura stale latente, no un flash visible hoy—. Este
    // test cubre el contrato del pre-paint de a11y (que no tenía cobertura), que
    // a11y-init.ts advierte que puede "romperse en silencio" si una key cambia.
    await page.route("**/_next/**/*.js", (route) => route.abort());
    await page.goto("/test-ds", { waitUntil: "domcontentloaded" });

    const html = page.locator("html");
    await expect(html).toHaveClass(/text-size-lg/);
    await expect(html).toHaveClass(/theme-high-contrast/);
    await expect(html).toHaveClass(/motion-off/);
    // El server-render trae text-size-md; el pre-paint debe haberlo reemplazado.
    await expect(html).not.toHaveClass(/text-size-md/);
  });
});
