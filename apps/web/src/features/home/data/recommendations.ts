import type { ModeId } from "@/components/ui/modes";

export type Recommendation = {
  id: string;
  title: string;
  subtitle: string;
  modeId: ModeId;
  /** Texto que prefillea el ChatInputDocked al elegir la card. */
  prefillPrompt: string;
};

/**
 * Catálogo de recomendaciones del home vacío (plan §5.3). Cada una arranca
 * una conversación en su modo. El backend real las reemplaza más adelante;
 * por ahora son el seed de "para arrancar".
 */
export const RECOMMENDATIONS: readonly Recommendation[] = [
  {
    id: "agendar",
    title: "Agendame algo",
    subtitle: "Probá pedirle al modo productividad",
    modeId: "productividad",
    prefillPrompt: "Agendame ",
  },
  {
    id: "foco",
    title: "Bloqueame 2 horas de foco",
    subtitle: "Productividad, bloque profundo",
    modeId: "productividad",
    prefillPrompt: "Bloqueame 2 horas de foco mañana a la ",
  },
  {
    id: "explicar",
    title: "Explicame un tema",
    subtitle: "El modo estudio te tutorea",
    modeId: "estudio",
    prefillPrompt: "Explicame ",
  },
  {
    id: "como-estas",
    title: "¿Cómo estás?",
    subtitle: "Charla casual, sin presión",
    modeId: "bienestar",
    prefillPrompt: "Hola, ¿cómo estás?",
  },
  {
    id: "que-paso-hoy",
    title: "Contame qué pasó hoy",
    subtitle: "Te acompaño un rato",
    modeId: "bienestar",
    prefillPrompt: "Hoy me pasó que ",
  },
  {
    id: "recomendar",
    title: "Recomendame algo para ver",
    subtitle: "Charla y sugerencias",
    modeId: "vida",
    prefillPrompt: "Recomendame algo para ver esta noche, me gusta ",
  },
  {
    id: "recorda-sobre-mi",
    title: "Recordá esto sobre mí",
    subtitle: "Memoria semántica explícita",
    modeId: "memoria",
    prefillPrompt: "Acordate de que ",
  },
  {
    id: "que-dije",
    title: "¿Qué dije la semana pasada?",
    subtitle: "Recall episódico",
    modeId: "memoria",
    prefillPrompt: "¿Qué te conté la semana pasada sobre ",
  },
] as const;

/**
 * Elige hasta {@link limit} recomendaciones priorizadas por los modos que
 * el usuario marcó como de interés (plan §5.3):
 *  - 1 modo elegido → hasta `limit` cards de ese modo.
 *  - 2+ modos → 1 card por modo (en orden de interés), y si sobra cupo se
 *    completa con cards extra de esos modos.
 *
 * Ambos casos caen en el mismo algoritmo de dos pasadas (con un solo modo,
 * la pasada de relleno completa hasta `limit` cards de ese modo).
 *
 * Si no hay modos de interés (no debería pasar: el onboarding pide ≥1),
 * cae a las primeras `limit` del catálogo.
 */
export function pickRecommendations(
  interestedModes: readonly ModeId[],
  limit = 4,
  catalog: readonly Recommendation[] = RECOMMENDATIONS,
): Recommendation[] {
  if (interestedModes.length === 0) return catalog.slice(0, limit);

  // Pre-agrupo por modo una sola vez para no re-filtrar el catálogo.
  const byMode = new Map<ModeId, Recommendation[]>();
  for (const rec of catalog) {
    const list = byMode.get(rec.modeId);
    if (list) list.push(rec);
    else byMode.set(rec.modeId, [rec]);
  }

  const picked: Recommendation[] = [];
  const used = new Set<string>();

  // Primera pasada: una card por modo de interés.
  for (const mode of interestedModes) {
    const first = byMode.get(mode)?.find((r) => !used.has(r.id));
    if (first) {
      picked.push(first);
      used.add(first.id);
      if (picked.length >= limit) return picked;
    }
  }

  // Segunda pasada: rellenar cupo con cards extra de los modos de interés.
  for (const mode of interestedModes) {
    for (const rec of byMode.get(mode) ?? []) {
      if (used.has(rec.id)) continue;
      picked.push(rec);
      used.add(rec.id);
      if (picked.length >= limit) return picked;
    }
  }

  return picked;
}
