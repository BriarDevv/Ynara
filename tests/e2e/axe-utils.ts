import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

/**
 * Helpers de axe compartidos por los specs e2e (onboarding.spec, a11y.spec).
 * Vive en un módulo NO-spec a propósito: Playwright prohíbe que un archivo de
 * test importe a otro archivo de test (ambos matchean `**​/*.spec.ts`).
 */

/**
 * Una violation de axe, derivada del tipo de retorno de `AxeBuilder.analyze()`
 * sin importar `axe-core` directo (es dep transitiva de @axe-core/playwright;
 * importarla acá sería frágil en la resolución de módulos del runner e2e).
 */
export type AxeViolation = Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"][number];

/**
 * Criterio de fallo del gate de axe (PR #11): falla ante CUALQUIER violation
 * `critical`, y además ante `color-contrast` de impacto `serious`. El QA de
 * contraste subió el texto "soft"/placeholder a AA, así que las regresiones de
 * contraste deben gatear. El resto de las `serious` (no-contraste) siguen
 * fuera del gate por ahora.
 */
export function isGatedViolation(v: AxeViolation): boolean {
  if (v.impact === "critical") return true;
  return v.impact === "serious" && v.id === "color-contrast";
}

/**
 * Corre axe (wcag2a/wcag2aa) sobre la página y devuelve solo las violations
 * que gatean el test (ver isGatedViolation).
 *
 * LÍMITE conocido: axe resuelve el fondo por el stack de pintado, así que NO
 * puede medir el contraste del texto que se apoya sobre el fondo vivo
 * (`LivingField` translúcido, `aria-hidden -z-10`, sin bg sólido): lo manda a
 * `results.incomplete`, no a `violations`. Por eso el gate cubre el texto sobre
 * superficies sólidas (cards, Noche, onboarding); el texto sobre el canvas lo
 * garantiza la calibración del token `--color-ink-soft` (0.70 pasa AA sobre el
 * canvas marfil), no esta verificación. Ver DESIGN.md §3.5.
 */
export async function gatedViolations(page: Page): Promise<AxeViolation[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  return results.violations.filter(isGatedViolation);
}
