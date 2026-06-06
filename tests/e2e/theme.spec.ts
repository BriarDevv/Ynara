import { expect, test } from "@playwright/test";

/**
 * E2E del tema Noche (DESIGN.md §3.1 / §16 #4).
 *
 * Cubre las tres patas del sistema de tema:
 *   (a) pre-paint: con `ynara.theme` persistido en dark, html.theme-dark
 *       está aplicado ANTES de que hidrate React (anti-FOUC, la landmine
 *       alta del plan);
 *   (b) toggle: el switch de /test-ds alterna la clase y el data-theme;
 *   (c) persistencia: la elección sobrevive al reload vía localStorage.
 *
 * Corre contra el dev de apps/web con MSW activo (ver playwright.config.ts).
 */

/** Formato de zustand/persist para la key ynara.theme. */
const DARK_PERSISTED = JSON.stringify({ state: { theme: "dark" }, version: 0 });

test.describe("tema Noche", () => {
  test("pre-paint: el tema persistido se aplica antes de hidratar (sin FOUC)", async ({ page }) => {
    // Sembrar la preferencia ANTES de cargar el documento.
    await page.addInitScript((value) => {
      localStorage.setItem("ynara.theme", value);
    }, DARK_PERSISTED);

    await page.goto("/test-ds", { waitUntil: "domcontentloaded" });

    // Sin esperar hidratación: el script inline del <head> ya tuvo que
    // aplicar la clase y el data-theme. Si esto falla, hay flash claro→oscuro.
    const htmlClass = await page.evaluate(() => document.documentElement.className);
    const dataTheme = await page.evaluate(() => document.documentElement.dataset.theme);
    expect(htmlClass).toContain("theme-dark");
    expect(dataTheme).toBe("dark");
  });

  test("toggle: el switch de /test-ds alterna claro ↔ Noche y persiste", async ({ page }) => {
    await page.goto("/test-ds");

    // Default claro (§3.1): sin clase ni preferencia previa.
    await expect(page.locator("html")).not.toHaveClass(/theme-dark/);

    // El toggle vive dentro del contenido (espera a mocksReady + hidratación).
    const toggle = page.getByRole("button", { name: "Tema: claro" });
    await toggle.click();

    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("button", { name: "Tema: Noche" })).toBeVisible();

    // Persistencia: tras reload el pre-paint restituye Noche.
    await page.reload({ waitUntil: "domcontentloaded" });
    const htmlClass = await page.evaluate(() => document.documentElement.className);
    expect(htmlClass).toContain("theme-dark");

    // Vuelta a claro desde el switch.
    await page.getByRole("button", { name: "Tema: Noche" }).click();
    await expect(page.locator("html")).not.toHaveClass(/theme-dark/);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("las superficies cambian con el tema (token re-declarado)", async ({ page }) => {
    await page.goto("/test-ds");
    const canvasLight = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--color-bg-canvas").trim(),
    );
    expect(canvasLight).toBe("#faf9f5");

    await page.getByRole("button", { name: "Tema: claro" }).click();
    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    const canvasDark = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--color-bg-canvas").trim(),
    );
    expect(canvasDark).toBe("#242c3f");
  });
});
