export type ModeId = "productividad" | "estudio" | "bienestar" | "vida" | "memoria";

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

export const MODES: readonly ModeDescriptor[] = [
  {
    id: "productividad",
    label: "Productividad",
    blurb: "Agendar, recordar, ejecutar.",
    tintVar: "var(--mode-productividad)",
    fillVar: "var(--mode-productividad-fill)",
  },
  {
    id: "estudio",
    label: "Estudio",
    blurb: "Tutoría, explicar, procesar textos.",
    tintVar: "var(--mode-estudio)",
    fillVar: "var(--mode-estudio-fill)",
  },
  {
    id: "bienestar",
    label: "Bienestar",
    blurb: "Descarga, acompañar.",
    tintVar: "var(--mode-bienestar)",
    fillVar: "var(--mode-bienestar-fill)",
  },
  {
    id: "vida",
    label: "Vida",
    blurb: "Charla casual, recomendaciones.",
    tintVar: "var(--mode-vida)",
    fillVar: "var(--mode-vida-fill)",
  },
  {
    id: "memoria",
    label: "Memoria",
    blurb: "Recordar conversaciones.",
    tintVar: "var(--mode-memoria)",
    fillVar: "var(--mode-memoria-fill)",
  },
] as const;

export const MODE_BY_ID: Record<ModeId, ModeDescriptor> = MODES.reduce(
  (acc, mode) => {
    acc[mode.id] = mode;
    return acc;
  },
  {} as Record<ModeId, ModeDescriptor>,
);

/**
 * Clima de dos tonos por modo — el gradiente ambiental del fondo vivo
 * (DESIGN.md §3.5, columna "Gradiente (clima del canvas)"). Vive SOLO en el
 * canvas de `LivingField` (§2); jamás como fill de UI (§3.4).
 *
 * Los valores van en hex literal (no `var(--color-*)`) porque el canvas 2D
 * necesita aritmética rgba por canal y no resuelve custom properties. La
 * fuente única sigue siendo la paleta de `globals.css`: el guard de
 * `globals.theme.test.ts` falla si estos pares se desincronizan de ella.
 */
export type ModeClimate = {
  /** Tono dominante (el acento del modo en el canvas). */
  readonly a: string;
  /** Tono acompañante del gradiente ambiental. */
  readonly b: string;
};

export const MODE_CLIMATE: Record<ModeId, ModeClimate> = {
  productividad: { a: "#2f5aa6", b: "#6e92cc" }, // azul → celeste
  estudio: { a: "#434a82", b: "#6e92cc" }, // índigo → celeste
  bienestar: { a: "#8165a3", b: "#8b9ad0" }, // violeta → lavanda
  vida: { a: "#5c6fb3", b: "#8165a3" }, // violáceo → violeta
  memoria: { a: "#6e92cc", b: "#8b9ad0" }, // celeste → lavanda
};
