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
