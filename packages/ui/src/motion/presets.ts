// Presets de motion compartidos (DESIGN.md §8). Son **valores**, no
// implementación: el web los consume con CSS/Motion y mobile con
// Reanimated. No atan ninguna librería (decisión F0.4: CSS-first).

/**
 * Modelo perceptual de spring (`visualDuration` + `bounce`), respaldado
 * por Apple WWDC23 + Figma (DESIGN.md §8.1). Más intuitivo que
 * stiffness/damping y portable entre Motion (web) y Reanimated (mobile).
 */
export type Spring = { visualDuration: number; bounce: number };

/** UI utilitaria: rápida, sin rebote. */
export const SPRING_SNAPPY: Spring = { visualDuration: 0.2, bounce: 0 };

/** Entradas y elementos amables: leve rebote. */
export const SPRING_SOFT: Spring = { visualDuration: 0.35, bounce: 0.15 };

/**
 * Duraciones en ms — espejo de los tokens `--duration-*` de globals.css
 * (DESIGN.md §8.1), para animaciones manejadas por JS.
 */
export const DURATION = {
  instant: 100,
  fast: 150,
  base: 200,
  slow: 300,
  screen: 350,
} as const;
export type DurationToken = keyof typeof DURATION;

/**
 * Easing default — espejo de `--ease-out-soft`
 * (`cubic-bezier(0.22, 1, 0.36, 1)`). Como puntos, para libs JS.
 */
export const EASE_OUT_SOFT = [0.22, 1, 0.36, 1] as const;
