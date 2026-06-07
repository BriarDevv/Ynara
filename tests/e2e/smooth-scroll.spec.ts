import { expect, type Page, test } from "@playwright/test";

/**
 * E2E del smooth-scroll de Lenis (DESIGN.md §8.4 / §16 #7), sobre `/hoy`
 * (vista del shell que scrollea en su `<main id="contenido">`).
 *
 *   (a) motion default: Lenis se monta sobre el `<main>` → la clase `lenis`
 *       aparece en el contenedor (rootElement = wrapper custom);
 *   (b) reduced-motion: NO se monta (scroll nativo) → sin clase `lenis`, mismo
 *       gate que el campo vivo (#5);
 *   (c) teclado (landmine (d) del plan): Lenis no intercepta el teclado, así
 *       que el contenedor sigue scrolleando con End/PageDown.
 *
 * Sembramos `ynara.user` con el onboarding completo para entrar directo a
 * `/hoy` sin recorrer el flujo (que además está roto en main, issue #180).
 * Corre contra el dev de apps/web con MSW activo (ver playwright.config.ts).
 */

/** Formato de zustand/persist para la key ynara.user (version 0 por defecto). */
const ONBOARDED = JSON.stringify({
  state: { onboardingCompleted: true, displayName: "Mateo" },
  version: 0,
});

/** Siembra el estado de usuario ANTES de cargar el documento. */
async function seedOnboarded(page: Page): Promise<void> {
  await page.addInitScript((value) => {
    localStorage.setItem("ynara.user", value);
  }, ONBOARDED);
}

const MAIN = "main#contenido";

test.describe("smooth-scroll", () => {
  test("monta Lenis sobre el <main> con motion default", async ({ page }) => {
    await seedOnboarded(page);
    await page.goto("/hoy");

    // Lenis agrega la clase `lenis` al wrapper al instanciarse (post-hidratación).
    await expect(page.locator(MAIN)).toHaveClass(/\blenis\b/);
  });

  test("con reduced-motion no monta Lenis (scroll nativo, sin clase)", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await seedOnboarded(page);
    await page.goto("/hoy");

    // Esperamos a que la vista hidrate (el h1 "Hoy" siempre está) para que la
    // ausencia de la clase sea significativa, no un estado pre-hidratación.
    await expect(page.getByRole("heading", { level: 1, name: "Hoy" })).toBeVisible();
    await expect(page.locator(MAIN)).not.toHaveClass(/\blenis\b/);
  });

  test("el teclado sigue scrolleando el contenedor (Lenis no lo intercepta)", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 420 });
    await seedOnboarded(page);
    await page.goto("/hoy");
    await expect(page.locator(MAIN)).toHaveClass(/\blenis\b/);

    const main = page.locator(MAIN);
    // El viewport chico fuerza overflow; si no scrollea, el test debe fallar.
    expect(await main.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);

    // Enfocar el contenedor (tabindex solo para el test) y scrollear por teclado.
    const before = await main.evaluate((el) => {
      (el as HTMLElement).tabIndex = -1;
      el.focus();
      return el.scrollTop;
    });
    await page.keyboard.press("End");
    await expect.poll(async () => main.evaluate((el) => el.scrollTop)).toBeGreaterThan(before);
  });

  test("la rueda scrollea el <main> (Lenis con su rAF corriendo)", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 420 });
    await seedOnboarded(page);
    await page.goto("/hoy");
    const main = page.locator(MAIN);
    await expect(main).toHaveClass(/\blenis\b/);
    expect(await main.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);

    // Rueda sobre el contenido: Lenis intercepta el wheel y, con su rAF corriendo
    // (autoRaf), anima el scrollTop. Sin el driver de rAF el wheel quedaría
    // preventDefault'd sin avanzar — este assert lo caza.
    const box = await main.boundingBox();
    if (!box) throw new Error("el <main> no tiene boundingBox");
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, 600);
    await expect.poll(async () => main.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  });
});
