import type { Mode } from "@ynara/shared-schemas";

/**
 * Descriptores de los modos para la UI mobile (label + blurb) — fuente única,
 * espejo de apps/web/src/components/ui/modes.ts. La consumen el onboarding
 * (ModesStep) y el chat (selector + ModeChip). El orden sigue ynara.config.json.
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
  (acc, m) => {
    acc[m.id] = m;
    return acc;
  },
  {} as Record<Mode, ModeDescriptor>,
);

/**
 * Clase NativeWind del dot/acento por modo. Mapa estático: NativeWind necesita
 * el className literal en build time (no `bg-mode-${id}` dinámico).
 */
export const MODE_DOT_CLASS: Record<Mode, string> = {
  productividad: "bg-mode-productividad",
  estudio: "bg-mode-estudio",
  bienestar: "bg-mode-bienestar",
  vida: "bg-mode-vida",
  memoria: "bg-mode-memoria",
};
