import type { Mode } from "@ynara/shared-schemas";

/**
 * `@ynara/core/features/modes` — **fuente única** de la tabla de descriptores
 * de modos (id/label/blurb + orden + `DEFAULT_MODE`) compartida por web, mobile
 * y admin. Antes estaba copiada a mano en cada app; acá vive el copy canónico.
 *
 * Cada app agrega SOLO sus campos de presentación encima de esto:
 * - web/admin: `tintVar`/`fillVar` (CSS vars del tint plano, DESIGN.md §3.5).
 * - mobile: `MODE_DOT_CLASS` (className NativeWind del dot).
 *
 * No exporta nada de DOM/React: es data pura + tipos.
 */
export type ModeDescriptor = {
  id: Mode;
  label: string;
  blurb: string;
};

export const MODE_DESCRIPTORS: readonly ModeDescriptor[] = [
  { id: "productividad", label: "Productividad", blurb: "Agendar, recordar, ejecutar." },
  { id: "estudio", label: "Estudio", blurb: "Tutoría, explicar, procesar textos." },
  { id: "bienestar", label: "Bienestar", blurb: "Descarga, acompañar." },
  { id: "vida", label: "Vida", blurb: "Charla casual, recomendaciones." },
  { id: "memoria", label: "Memoria", blurb: "Recordar conversaciones." },
] as const;

export const MODE_BY_ID: Record<Mode, ModeDescriptor> = MODE_DESCRIPTORS.reduce(
  (acc, mode) => {
    acc[mode.id] = mode;
    return acc;
  },
  {} as Record<Mode, ModeDescriptor>,
);

/** Modo pre-marcado por default en el step de modos del onboarding. */
export const DEFAULT_MODE: Mode = "productividad";
