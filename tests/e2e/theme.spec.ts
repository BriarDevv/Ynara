import { expect, test } from "@playwright/test";

/**
 * E2E del tema Noche (DESIGN.md §3.1 / §16 #4).
 *
 * Cubre las tres patas del sistema de tema:
 *   (a) pre-paint: con `ynara.theme` persistido en dark, html.theme-dark
 *       está aplicado por el <script> inline del <head> — se verifica con
 *       los chunks de Next ABORTADOS, así React nunca hidrata y la clase
 *       solo puede venir del pre-paint (anti-FOUC, la landmine alta del
 *       plan; sin el abort, el ThemeApplier post-hidratación daría falso
 *       verde);
 *   (b) toggle: el switch de /test-ds alterna la clase y el data-theme;
 *   (c) persistencia: la elección sobrevive al reload vía localStorage.
 *
 * Corre contra el dev de apps/web con MSW activo (ver playwright.config.ts).
 */

/** Formato de zustand/persist para la key ynara.theme. */
const DARK_PERSISTED = JSON.stringify({ state: { theme: "dark" }, version: 0 });

/** Nombre accesible ESTABLE del switch (el estado lo porta aria-pressed). */
const TOGGLE_NAME = "Cambiar tema";

test.describe("tema Noche", () => {
  test("pre-paint: el script inline aplica el tema persistido sin React (sin FOUC)", async ({
    page,
  }) => {
    // Sembrar la preferencia ANTES de cargar el documento.
    await page.addInitScript((value) => {
      localStorage.setItem("ynara.theme", value);
    }, DARK_PERSISTED);

    // Abortar los chunks JS de Next ANTES de navegar: React nunca hidrata,
    // así que si la clase aparece la puso el <script> inline del <head>
    // (el pre-paint real), no el ThemeApplier post-hidratación.
    await page.route("**/_next/**/*.js", (route) => route.abort());

    await page.goto("/test-ds", { waitUntil: "domcontentloaded" });

    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    // El token re-declarado ya rige el CSS computado antes de hidratar.
    const canvas = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--color-bg-canvas").trim(),
    );
    expect(canvas).toBe("#242c3f");
  });

  test("toggle: el switch de /test-ds alterna claro ↔ Noche y persiste", async ({ page }) => {
    await page.goto("/test-ds");

    // Default claro (§3.1): sin clase ni preferencia previa.
    await expect(page.locator("html")).not.toHaveClass(/theme-dark/);

    // El toggle vive dentro del contenido (espera a mocksReady + hidratación).
    const toggle = page.getByRole("button", { name: TOGGLE_NAME });
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
    await expect(toggle).toHaveText(/Tema: claro/);
    await toggle.click();

    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await expect(toggle).toHaveText(/Tema: Noche/);

    // Persistencia: tras reload el pre-paint restituye Noche.
    await page.reload({ waitUntil: "domcontentloaded" });
    const htmlClass = await page.evaluate(() => document.documentElement.className);
    expect(htmlClass).toContain("theme-dark");

    // Vuelta a claro desde el switch.
    await page.getByRole("button", { name: TOGGLE_NAME }).click();
    await expect(page.locator("html")).not.toHaveClass(/theme-dark/);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("las superficies cambian con el tema (token re-declarado)", async ({ page }) => {
    await page.goto("/test-ds");
    const canvasLight = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--color-bg-canvas").trim(),
    );
    expect(canvasLight).toBe("#faf9f5");

    await page.getByRole("button", { name: TOGGLE_NAME }).click();
    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    const canvasDark = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--color-bg-canvas").trim(),
    );
    expect(canvasDark).toBe("#242c3f");
  });
});
