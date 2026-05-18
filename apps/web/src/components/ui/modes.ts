export type ModeId = "productividad" | "estudio" | "bienestar" | "vida" | "memoria";

export type ModeDescriptor = {
  id: ModeId;
  label: string;
  blurb: string;
  /** Clase utility que aplica el gradiente del modo como background-image. */
  gradientClass: `bg-mode-${ModeId}`;
};

export const MODES: readonly ModeDescriptor[] = [
  {
    id: "productividad",
    label: "Productividad",
    blurb: "Agendar, recordar, ejecutar.",
    gradientClass: "bg-mode-productividad",
  },
  {
    id: "estudio",
    label: "Estudio",
    blurb: "Tutoría, explicar, procesar textos.",
    gradientClass: "bg-mode-estudio",
  },
  {
    id: "bienestar",
    label: "Bienestar",
    blurb: "Descarga, acompañar.",
    gradientClass: "bg-mode-bienestar",
  },
  {
    id: "vida",
    label: "Vida",
    blurb: "Charla casual, recomendaciones.",
    gradientClass: "bg-mode-vida",
  },
  {
    id: "memoria",
    label: "Memoria",
    blurb: "Recordar conversaciones.",
    gradientClass: "bg-mode-memoria",
  },
] as const;

export const MODE_BY_ID: Record<ModeId, ModeDescriptor> = MODES.reduce(
  (acc, mode) => {
    acc[mode.id] = mode;
    return acc;
  },
  {} as Record<ModeId, ModeDescriptor>,
);
