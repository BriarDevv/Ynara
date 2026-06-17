import type { ModeId } from "@/components/ui/modes";

/** Una acción que el usuario puede tomar desde la tarjeta de anticipación. */
export type AnticipationAction = {
  label: string;
  /** Si `true`, se renderiza con fondo sólido teñido por el modo. */
  primary?: boolean;
};

/** Anticipación proactiva de Ynara: algo que se adelanta a la necesidad. */
export type Anticipation = {
  id: string;
  /** Tipo mostrado en el badge (ej. "Anticipación", "Recordatorio"). */
  kind: string;
  /** Hora o referencia temporal (ej. "10:30", "en 15 min"). */
  time: string;
  /** Texto principal del aviso, en español rioplatense. */
  text: string;
  /** Modo que tiñe la card. */
  mode: ModeId;
  actions: AnticipationAction[];
};

/**
 * Anticipaciones canned para el mock de Hoy (no hay backend todavía).
 * Cuando el endpoint real exista se apaga esta función y la UI queda intacta.
 */
export function buildAnticipations(): Anticipation[] {
  return [
    {
      id: "ant-foco-001",
      kind: "Anticipación",
      time: "10:30",
      text: "Tenés 90 min libres antes de la reunión. ¿Bloqueo un tiempo de foco para la propuesta?",
      mode: "productividad",
      actions: [{ label: "Sí, bloquealo", primary: true }, { label: "Ahora no" }],
    },
    {
      id: "ant-pausa-001",
      kind: "Recordatorio",
      time: "12:00",
      text: "Llevás más de 2 horas en pantalla. Una pausa corta te ayuda a mantener el ritmo.",
      mode: "bienestar",
      actions: [{ label: "Listo, paro un rato", primary: true }, { label: "Ignorar" }],
    },
  ];
}
