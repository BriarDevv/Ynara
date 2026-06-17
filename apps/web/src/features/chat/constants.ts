// Re-export desde @ynara/core (ADR-012): constantes y copy canned del chat,
// compartidos con mobile. Se mantiene `@/features/chat/constants` (y los
// `../constants` relativos) como superficie estable.
export {
  AGENT_MODES,
  cannedActions,
  cannedReply,
  isAgentMode,
  MODE_INTRO,
} from "@ynara/core/features/chat";

import type { ModeId } from "@/components/ui/modes";

/**
 * Prompts sugeridos por modo para el estado vacío de la conversación.
 * Copy en rioplatense conversacional, alineado con el tono de cada modo
 * (docs/product/MODES.md). 4 prompts por modo, ordenados por frecuencia
 * de uso esperada.
 */
export const CHAT_PROMPTS: Record<ModeId, string[]> = {
  productividad: [
    "Armame una lista de tareas para hoy",
    "Agendame una reunión para mañana a las 10",
    "¿Qué tengo pendiente esta semana?",
    "Recordame llamar a las 18hs",
  ],
  estudio: [
    "Explicame qué es la fotosíntesis",
    "Haceme un resumen de este texto",
    "Dame tres preguntas de repaso sobre termodinámica",
    "¿Cómo funciona la programación orientada a objetos?",
  ],
  bienestar: [
    "Me siento un poco abrumado, ¿hablamos?",
    "¿Cómo puedo manejar mejor el estrés?",
    "Necesito ordenar mis pensamientos",
    "¿Qué puedo hacer para dormir mejor?",
  ],
  vida: [
    "Recomendame una serie para ver esta noche",
    "¿Qué puedo cocinar con lo que tengo en casa?",
    "Dame ideas de planes para el fin de semana",
    "¿Cómo aprendo a hacer sourdough?",
  ],
  memoria: [
    "¿Qué recordás de mis últimas conversaciones?",
    "Guardá esto: me gustan las películas de Kubrick",
    "¿Qué cosas importantes me dijiste antes?",
    "Recordame que mi cumpleaños es en julio",
  ],
};
