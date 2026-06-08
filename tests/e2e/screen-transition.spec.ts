import { expect, type Page, test } from "@playwright/test";

/**
 * E2E del crossfade / transición de pantalla (DESIGN.md §8.3 / §16 #8).
 *
 *   (a) navegación entre rutas del shell: el `template` del grupo `(app)`
 *       envuelve el contenido y se re-monta en cada navegación → la nueva
 *       pantalla entra con `anim-fade-up`;
 *   (b) toggle de tema: el cambio pasa por `document.startViewTransition`
 *       (crossfade root claro↔Noche) en un browser que lo soporta.
 *
 * Corre contra el dev de apps/web con MSW activo (ver playwright.config.ts).
 */

const ONBOARDED = JSON.stringify({
  state: { onboardingCompleted: true, displayName: "Mateo" },
  version: 0,
});

async function seedOnboarded(page: Page): Promise<void> {
  await page.addInitScript((value) => {
    localStorage.setItem("ynara.user", value);
  }, ONBOARDED);
}

const SCREEN = "main#contenido > .anim-screen-in";

test.describe("transición de pantalla", () => {
  test("la navegación entre rutas monta el template con la transición", async ({ page }) => {
    await seedOnboarded(page);
    await page.goto("/hoy");
    await expect(page.getByRole("heading", { level: 1, name: "Hoy" })).toBeVisible();
    // El template del grupo (app) envuelve el contenido con la entrada.
    await expect(page.locator(SCREEN)).toBeVisible();
    // La entrada es opacidad pura: SIN transform, para no convertir al template
    // en containing block de los overlays `fixed` (el welcome Toast). Guard de
    // regresión del MAYOR de la review.
    expect(await page.locator(SCREEN).evaluate((el) => getComputedStyle(el).transform)).toBe(
      "none",
    );

    // Navegar a otra ruta del shell (client-side): el template se re-monta.
    await page.getByRole("link", { name: "Agenda" }).click();
    await expect(page).toHaveURL(/\/agenda/);
    await expect(page.locator(SCREEN)).toBeVisible();
  });

  test("el toggle de tema pasa por document.startViewTransition (crossfade)", async ({ page }) => {
    // Envolver la API nativa ANTES de cargar para contar las invocaciones.
    await page.addInitScript(() => {
      const w = window as unknown as { __vtCalls: number };
      w.__vtCalls = 0;
      const doc = document as unknown as {
        startViewTransition?: (cb: () => void) => unknown;
      };
      const orig = doc.startViewTransition?.bind(document);
      if (orig) {
        doc.startViewTransition = (cb: () => void) => {
          w.__vtCalls += 1;
          return orig(cb);
        };
      }
    });
    await page.goto("/test-ds");

    const toggle = page.getByRole("button", { name: "Cambiar tema" });
    await expect(toggle).toBeVisible();
    await toggle.click();

    // El cambio efectivamente ocurrió y pasó por la View Transitions API.
    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    const vtCalls = await page.evaluate(
      () => (window as unknown as { __vtCalls: number }).__vtCalls,
    );
    expect(vtCalls).toBeGreaterThan(0);
  });
});
