import type { Mode } from "@ynara/shared-schemas";

/**
 * **Clima del campo vivo** (DESIGN.md §3.5) — el par de tonos del gradiente
 * ambiental por modo. Fuente ÚNICA compartida entre web (Canvas2D) y mobile
 * (Skia): los dos renderers tiñen el fondo con estos mismos hex, así el campo
 * queda idéntico en las dos plataformas.
 *
 * Hex literal (no `var(--color-*)`): el canvas necesita aritmética rgba por
 * canal y no resuelve custom properties. La paleta canónica vive en el design
 * system; estos pares deben mantenerse en sync con ella (guard en web).
 */
export type ModeClimate = {
  /** Tono dominante (el acento del modo en el canvas). */
  readonly a: string;
  /** Tono acompañante del gradiente ambiental. */
  readonly b: string;
};

export const MODE_CLIMATE: Record<Mode, ModeClimate> = {
  productividad: { a: "#2f5aa6", b: "#6e92cc" }, // azul → celeste
  estudio: { a: "#434a82", b: "#6e92cc" }, // índigo → celeste
  bienestar: { a: "#8165a3", b: "#8b9ad0" }, // violeta → lavanda
  vida: { a: "#5c6fb3", b: "#8165a3" }, // violáceo → violeta
  memoria: { a: "#6e92cc", b: "#8b9ad0" }, // celeste → lavanda
};

export type Rgb = readonly [number, number, number];

/** "#rrggbb" → [r,g,b] (0-255). Sin alpha; cada renderer arma su rgba. */
export function hexToRgb(hex: string): Rgb {
  const h = hex.replace("#", "");
  return [
    Number.parseInt(h.slice(0, 2), 16),
    Number.parseInt(h.slice(2, 4), 16),
    Number.parseInt(h.slice(4, 6), 16),
  ];
}

/**
 * Punto de luz de los nodos: azul tinta en claro, lavanda pálida en Noche.
 * Compartido para que el titileo de los nodos sea del mismo color en ambas
 * plataformas.
 */
export function dotColor(dark: boolean): Rgb {
  return dark ? [200, 212, 245] : [70, 96, 166];
}
