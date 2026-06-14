import type { Mode } from "@ynara/shared-schemas";

/**
 * Descriptores visuales de los modos para el onboarding (mobile). Labels y
 * blurbs verbatim de apps/web/src/components/ui/modes.ts. El orden sigue al de
 * ynara.config.json (fuente canónica de qué modos existen).
 */
export type ModeOption = {
  id: Mode;
  label: string;
  blurb: string;
};

export const MODE_OPTIONS: readonly ModeOption[] = [
  { id: "productividad", label: "Productividad", blurb: "Agendar, recordar, ejecutar." },
  { id: "estudio", label: "Estudio", blurb: "Tutoría, explicar, procesar textos." },
  { id: "bienestar", label: "Bienestar", blurb: "Descarga, acompañar." },
  { id: "vida", label: "Vida", blurb: "Charla casual, recomendaciones." },
  { id: "memoria", label: "Memoria", blurb: "Recordar conversaciones." },
] as const;

/** Modo pre-marcado por default en el step de modos (igual que la web). */
export const DEFAULT_MODE: Mode = "productividad";

/**
 * Clase NativeWind del dot de color por modo. Mapa estático porque NativeWind
 * necesita el className literal en build time (no `bg-mode-${id}` dinámico).
 */
export const MODE_DOT_CLASS: Record<Mode, string> = {
  productividad: "bg-mode-productividad",
  estudio: "bg-mode-estudio",
  bienestar: "bg-mode-bienestar",
  vida: "bg-mode-vida",
  memoria: "bg-mode-memoria",
};
