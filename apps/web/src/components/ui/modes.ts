import { DEFAULT_MODE, MODE_DESCRIPTORS } from "@ynara/core/features/modes";
import type { Mode } from "@ynara/shared-schemas";

/**
 * `ModeId` = el enum `Mode` de `@ynara/shared-schemas` (la misma union de
 * strings de siempre). Se mantiene el alias para no tocar los consumidores ni
 * los template-literal types `var(--mode-${ModeId})`.
 */
export type ModeId = Mode;

export type ModeDescriptor = {
  id: ModeId;
  label: string;
  blurb: string;
  /**
   * Color plano ambiental del modo (dot, hairline, tint de chip) — DESIGN.md
   * §3.5. Se consume como `style={{ backgroundColor: mode.tintVar }}`.
   */
  tintVar: `var(--mode-${ModeId})`;
  /**
   * Tono del modo que puede llevar texto blanco encima (AA ≥4.5:1) — §3.5.
   * Solo Memoria difiere del tint (lavanda-deep); el resto comparte tono.
   */
  fillVar: `var(--mode-${ModeId}-fill)`;
};

/**
 * Tabla visual de los modos. El copy (label/blurb/orden) viene de la **fuente
 * única** en `@ynara/core/features/modes`; acá sólo se agregan los campos de
 * presentación web (`tintVar`/`fillVar`).
 */
export const MODES: readonly ModeDescriptor[] = MODE_DESCRIPTORS.map((d) => ({
  id: d.id,
  label: d.label,
  blurb: d.blurb,
  tintVar: `var(--mode-${d.id})`,
  fillVar: `var(--mode-${d.id}-fill)`,
}));

export const MODE_BY_ID: Record<ModeId, ModeDescriptor> = MODES.reduce(
  (acc, mode) => {
    acc[mode.id] = mode;
    return acc;
  },
  {} as Record<ModeId, ModeDescriptor>,
);

/**
 * Clima de dos tonos por modo (gradiente ambiental del campo vivo, DESIGN.md
 * §3.5). **Fuente única en `@ynara/core/features/field`** — compartida con el
 * render de mobile (Skia) para que el fondo quede idéntico en las dos
 * plataformas. Se re-exporta acá para no romper los imports existentes desde
 * `@/components/ui/modes`. El guard de `globals.theme.test.ts` sigue validando
 * que estos pares estén en sync con la paleta de `globals.css`.
 */
export { MODE_CLIMATE, type ModeClimate } from "@ynara/core/features/field";
/** Re-export de la fuente única para los consumidores que importan desde acá. */
export { DEFAULT_MODE };
