import type { Mode } from "@ynara/shared-schemas";

/**
 * Colores de marca para usos **nativos** donde NativeWind no aplica: style props
 * de RN (`backgroundColor`, etc.) y props que piden un valor crudo
 * (`placeholderTextColor`, React Navigation que no toma classNames). Espejan los
 * tokens de `tailwind.config.js` / `global.css` — fuente única para no hardcodear
 * hex sueltos que terminen divergiendo del tema.
 */

/** Acento por modo (= `colors.mode.*` del tailwind.config). */
export const MODE_COLOR: Record<Mode, string> = {
  productividad: "#2f5aa6",
  estudio: "#434a82",
  bienestar: "#8165a3",
  vida: "#5c6fb3",
  memoria: "#8b9ad0",
};

/** Texto tenue / placeholder (= `--color-ink-muted` del tema oscuro). */
export const INK_MUTED = "#7c84a0";
