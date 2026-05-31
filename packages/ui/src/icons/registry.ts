import type { IconName, IconShape } from "./types";

/**
 * Geometría del set de íconos, grilla `44×44`.
 *
 * Los 10 íconos de marca (idea…red) son la **geometría literal** de la
 * guía de identidad visual (lámina 08 · Iconografía): trazo uniforme y el
 * diamante como acento (lo encarna `foco`, un cuadrado rotado 45°, y la
 * capa superior de `memoria`).
 *
 * Los 5 utilitarios (enviar…chevron) no están en la guía: se diseñaron en
 * la misma grilla y trazo para convivir sin costura. Reemplazan los
 * "tells" amateur del código actual (flechas `→ ← ↓` como íconos, §9).
 */
export const ICON_SHAPES: Record<IconName, readonly IconShape[]> = {
  // — Set de marca —
  idea: [
    { type: "circle", cx: 22, cy: 19, r: 10 },
    { type: "path", d: "M17 32h10M18.5 36h7" },
  ],
  conexion: [
    { type: "circle", cx: 12, cy: 22, r: 5.5 },
    { type: "circle", cx: 32, cy: 22, r: 5.5 },
    { type: "path", d: "M17.5 22h9" },
  ],
  memoria: [
    { type: "path", d: "M8 16 22 9 36 16 22 23Z" },
    { type: "path", d: "M8 23 22 30 36 23" },
    { type: "path", d: "M8 30 22 37 36 30" },
  ],
  nota: [
    { type: "rect", x: 11, y: 8, w: 22, h: 28, rx: 3 },
    { type: "path", d: "M16 16h12M16 21h12M16 26h8" },
  ],
  buscar: [
    { type: "circle", cx: 19, cy: 19, r: 9 },
    { type: "path", d: "M26 26 35 35" },
  ],
  dialogo: [
    {
      type: "path",
      d: "M9 12h26a3 3 0 0 1 3 3v13a3 3 0 0 1-3 3H21l-7 6v-6h-5a3 3 0 0 1-3-3V15a3 3 0 0 1 3-3Z",
    },
  ],
  recordatorio: [
    { type: "circle", cx: 22, cy: 23, r: 13 },
    { type: "path", d: "M22 15v8l6 4" },
  ],
  adaptacion: [
    { type: "path", d: "M10 19a12 12 0 0 1 21-7" },
    { type: "path", d: "M25 5l7 7-7 4" },
    { type: "path", d: "M34 25a12 12 0 0 1-21 7" },
    { type: "path", d: "M19 39l-7-7 7-4" },
  ],
  foco: [
    { type: "rect", x: 13, y: 13, w: 18, h: 18, rx: 4, rotate: 45 },
    { type: "circle", cx: 22, cy: 22, r: 3.4 },
  ],
  red: [
    { type: "circle", cx: 22, cy: 11, r: 3.4 },
    { type: "circle", cx: 11, cy: 32, r: 3.4 },
    { type: "circle", cx: 33, cy: 32, r: 3.4 },
    { type: "path", d: "M22 11 11 32M22 11 33 32M11 32h22" },
  ],

  // — Utilitarios (misma grilla/trazo) —
  enviar: [
    { type: "path", d: "M6 23 38 7 29 38 21 27Z" },
    { type: "path", d: "M38 7 21 27" },
  ],
  detener: [{ type: "rect", x: 14, y: 14, w: 16, h: 16, rx: 3 }],
  atras: [{ type: "path", d: "M26 12 15 22 26 32" }],
  cerrar: [{ type: "path", d: "M14 14 30 30M30 14 14 30" }],
  chevron: [{ type: "path", d: "M12 18 22 28 32 18" }],
};

/** Orden de iteración estable (showcase/grid, tests). */
export const ICON_NAMES = Object.keys(ICON_SHAPES) as IconName[];
