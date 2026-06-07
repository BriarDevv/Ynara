import { expect, test } from "@playwright/test";

/**
 * E2E del fondo vivo (DESIGN.md §2 / §16 #5), contra la vitrina de /test-ds
 * (5 variantes montadas, la primera es `aurora`).
 *
 *   (a) decorativo: el canvas vive dentro de un wrapper `aria-hidden` con
 *       `pointer-events: none` — jamás compite con el contenido (§2.3);
 *   (b) reduced-motion: con la emulación activa el campo dibuja UN frame
 *       estático — dos muestras del canvas separadas en el tiempo son
 *       bit-idénticas (el rAF no corre, landmine (a) del plan);
 *   (c) motion default: el campo anima — las mismas muestras difieren.
 *
 * Corre contra el dev de apps/web con MSW activo (ver playwright.config.ts).
 */

/** Espera a que el primer canvas haya pasado por resize() (efecto montado)
 *  y a que las webfonts hayan cargado (sus reflows disparan ResizeObserver;
 *  muestrear antes haría diff de layout, no de animación). */
async function waitForFieldReady(page: import("@playwright/test").Page): Promise<void> {
  await page.waitForFunction(() => {
    const c = document.querySelector("canvas");
    return Boolean(c && c.width > 0);
  });
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

/** Muestra bit-exacta del primer canvas de la página (la caja `aurora`). */
function sampleField(page: import("@playwright/test").Page): Promise<string> {
  return page.evaluate(() => {
    const c = document.querySelector("canvas") as HTMLCanvasElement;
    return c.toDataURL();
  });
}

test.describe("fondo vivo", () => {
  test("es decoración pura: aria-hidden y pointer-events none, una caja por variante", async ({
    page,
  }) => {
    await page.goto("/test-ds");
    await waitForFieldReady(page);

    // La vitrina monta las 5 variantes (§2.2).
    await expect(page.locator("canvas")).toHaveCount(5);

    const wrapper = await page.evaluate(() => {
      const canvas = document.querySelector("canvas");
      const host = canvas?.closest("[aria-hidden]");
      return host
        ? { found: true, pointerEvents: getComputedStyle(host).pointerEvents }
        : { found: false, pointerEvents: "" };
    });
    expect(wrapper.found).toBe(true);
    expect(wrapper.pointerEvents).toBe("none");
  });

  test("con reduced-motion dibuja un único frame estático (el rAF no corre)", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/test-ds");
    await waitForFieldReady(page);

    const before = await sampleField(page);
    await page.waitForTimeout(700);
    const after = await sampleField(page);
    expect(after).toBe(before);
  });

  test("sin reduce el campo respira: dos muestras separadas difieren", async ({ page }) => {
    await page.goto("/test-ds");
    await waitForFieldReady(page);

    const before = await sampleField(page);
    await page.waitForTimeout(700);
    const after = await sampleField(page);
    expect(after).not.toBe(before);
  });
});
