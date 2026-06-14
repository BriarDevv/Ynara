import type { Action, Mode } from "@ynara/shared-schemas";

/**
 * Constantes y copy canned del chat, compartidas web + mobile (ADR-012).
 * Fuera de los componentes y del mock para no duplicar texto y facilitar i18n
 * futuro. El copy refleja el tono de cada modo (ver `docs/product/MODES.md`).
 */

/**
 * Modos que corren sobre Qwen (agente): ejecutan tools y producen `actions`.
 * Los demás (Gemma) solo conversan → `actions: []`. Fuente: ADR-002 +
 * `ynara.config.json[modes]`. Acá se listan explícitos porque el frontend no
 * lee `ynara.config.json` en runtime; si cambia el routing, actualizar acá.
 */
export const AGENT_MODES: readonly Mode[] = ["productividad", "memoria"] as const;

/** True si el modo ejecuta tools (Qwen) y por ende puede emitir `actions`. */
export function isAgentMode(mode: Mode): boolean {
  return AGENT_MODES.includes(mode);
}

/** Intro del estado vacío de la conversación, por modo. */
export const MODE_INTRO: Record<Mode, string> = {
  productividad: "Estás en modo Productividad. Decime qué agendar o recordar y lo armo.",
  estudio: "Estás en modo Estudio. Tirame un tema y lo desarmamos juntos.",
  bienestar: "Estás en modo Bienestar. Contame cómo venís; te escucho.",
  vida: "Estás en modo Vida. ¿De qué tenés ganas de hablar?",
  memoria: "Estás en modo Memoria. Pedime que recuerde algo o que te lo traiga de vuelta.",
};

/**
 * Respuesta canned del mock, por modo. Es placeholder hasta que `/v1/chat`
 * real (M9) responda; mantiene el tono de cada modo para que la UI se vea
 * coherente mientras tanto. No pretende ser una respuesta "inteligente".
 */
// Plantilla por modo. Record keyed por Mode → exhaustivo por tipo: si se
// agrega un modo, esto deja de compilar hasta cubrirlo (consistente con
// cannedActions y MODE_INTRO).
const CANNED_REPLY: Record<Mode, (echo: string) => string> = {
  productividad: (echo) => `Dale, me ocupo de "${echo}". Te dejo la acción anotada acá abajo.`,
  estudio: (echo) => `Buena. Arranquemos por "${echo}": primero la idea base y después un ejemplo.`,
  bienestar: (echo) => `Te leo. Lo de "${echo}" pesa; contame un poco más si querés.`,
  vida: (echo) => `Mirá, sobre "${echo}" se me ocurren un par de cosas. ¿Vamos viendo?`,
  memoria: (echo) => `Anotado lo de "${echo}". Lo guardo para traértelo cuando lo necesites.`,
};

export function cannedReply(mode: Mode, userText: string): string {
  const echo = userText.trim().slice(0, 80);
  return CANNED_REPLY[mode](echo);
}

/**
 * Acciones canned del mock para modos Qwen. `result` queda en el stub
 * `{ status: "not_wired" }` igual que `ToolRegistry.execute` hoy en el
 * backend; el real llega cuando se cableen las tools. Gemma → `[]`.
 */
export function cannedActions(mode: Mode): Action[] {
  switch (mode) {
    case "productividad":
      return [
        {
          id: "call_mock_calendar",
          name: "calendar.create_event",
          arguments: { title: "Recordatorio de ejemplo", start: "2026-06-01T10:00:00Z" },
          result: { status: "not_wired" },
        },
      ];
    case "memoria":
      return [
        {
          id: "call_mock_memory",
          name: "memory.write",
          arguments: { content: "Hecho de ejemplo para recordar" },
          result: { status: "not_wired" },
        },
      ];
    default:
      return [];
  }
}
