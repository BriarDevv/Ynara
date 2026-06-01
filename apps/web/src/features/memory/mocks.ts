import type {
  EpisodicMemoryOut,
  MemoryList,
  ProceduralMemoryOut,
  SemanticMemoryOut,
} from "@ynara/shared-schemas";
import { HttpResponse, http } from "msw";
import { env } from "@/lib/env";

/**
 * Handlers MSW + fixtures de la memoria.
 *
 * SHAPES espejan el contrato REAL de `/v1/memory` (`apps/backend/docs/ENDPOINTS.md`,
 * `app/schemas/memory.py`) — a diferencia de la búsqueda (endpoint todavía
 * inexistente), list y detail SÍ existen en el backend; el mock solo permite
 * construir la UI sin levantar Postgres. Al apuntar al backend real (apagar el
 * toggle de mocks) la UI no cambia.
 *
 * Las fechas se generan relativas a `now` para que el timeline muestre buckets
 * vivos (Hoy / Esta semana / …) en cualquier momento que se abra la demo.
 */

const apiUrl = (path: string) => `${env.NEXT_PUBLIC_API_URL}${path}`;

// UUIDs estables: el detalle (`/v1/memory/{layer}/{ref}`) los reusa para
// resolver una entrada puntual. No cambiar sin actualizar los links de prueba.
const USER_ID = "0193f000-0000-7000-8000-000000000001";
export const MEMORY_IDS = {
  semTesis: "0193f001-0000-7000-8000-000000000001",
  semJerga: "0193f001-0000-7000-8000-000000000002",
  semObjetivo: "0193f001-0000-7000-8000-000000000003",
  epiBrief: "0193f002-0000-7000-8000-000000000001",
  epiKickoff: "0193f002-0000-7000-8000-000000000002",
  sessBrief: "0193f0aa-0000-7000-8000-000000000001",
  sessKickoff: "0193f0aa-0000-7000-8000-000000000002",
} as const;

const DAY_MS = 24 * 60 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

/** ISO a `now` menos un offset en días/horas. */
function ago(now: Date, { days = 0, hours = 0 }: { days?: number; hours?: number }): string {
  return new Date(now.getTime() - days * DAY_MS - hours * HOUR_MS).toISOString();
}

/** Dataset de demostración de las 3 capas, fechado relativo a `now`. */
export function buildMemoryList(now: Date): MemoryList {
  const semantic: SemanticMemoryOut[] = [
    {
      id: MEMORY_IDS.semTesis,
      user_id: USER_ID,
      content: "Decidiste arrancar la tesis por el capítulo 3 antes que el 2.",
      importance: 80,
      source_session_id: MEMORY_IDS.sessKickoff,
      created_at: ago(now, { hours: 2 }),
      updated_at: ago(now, { hours: 2 }),
    },
    {
      id: MEMORY_IDS.semJerga,
      user_id: USER_ID,
      content: "Preferís que te evite la jerga técnica cuando hablás del cliente Õmi.",
      importance: 65,
      source_session_id: MEMORY_IDS.sessBrief,
      created_at: ago(now, { days: 4 }),
      updated_at: ago(now, { days: 4 }),
    },
    {
      id: MEMORY_IDS.semObjetivo,
      user_id: USER_ID,
      content: "Tu objetivo de este trimestre es cerrar el marco teórico de la tesis.",
      importance: 70,
      source_session_id: null,
      created_at: ago(now, { days: 20 }),
      updated_at: ago(now, { days: 20 }),
    },
  ];

  const episodic: EpisodicMemoryOut[] = [
    {
      id: MEMORY_IDS.epiBrief,
      user_id: USER_ID,
      session_id: MEMORY_IDS.sessBrief,
      summary:
        "Charlaron sobre cómo encarar el brief de Õmi. Quedaste en mover la entrega una semana.",
      is_sensitive: false,
      retention_days: 365,
      occurred_at: ago(now, { days: 1 }),
      topics: { proyecto: "omi", tipo: "decisión" },
      created_at: ago(now, { days: 1 }),
      updated_at: ago(now, { days: 1 }),
    },
    {
      id: MEMORY_IDS.epiKickoff,
      user_id: USER_ID,
      session_id: MEMORY_IDS.sessKickoff,
      summary: "Repasaste el kickoff del proyecto y anotaste las dudas para la reunión del lunes.",
      is_sensitive: false,
      retention_days: 365,
      occurred_at: ago(now, { days: 6 }),
      topics: { proyecto: "tesis", tipo: "repaso" },
      created_at: ago(now, { days: 6 }),
      updated_at: ago(now, { days: 6 }),
    },
  ];

  const procedural: ProceduralMemoryOut[] = [
    {
      id: "0193f003-0000-7000-8000-000000000001",
      user_id: USER_ID,
      key: "foco_horario",
      value: { preferencia: "mañana", confirmado_dias: 3 },
      confidence: 0.86,
      last_reinforced_at: ago(now, { days: 3 }),
      stale: false,
      created_at: ago(now, { days: 30 }),
      updated_at: ago(now, { days: 3 }),
    },
    {
      id: "0193f003-0000-7000-8000-000000000002",
      user_id: USER_ID,
      key: "tono_cliente_omi",
      value: { evitar: "jerga técnica", preferir: "lenguaje llano" },
      confidence: 0.62,
      last_reinforced_at: ago(now, { days: 45 }),
      stale: true,
      created_at: ago(now, { days: 60 }),
      updated_at: ago(now, { days: 45 }),
    },
  ];

  return {
    semantic: { items: semantic, total: semantic.length },
    episodic: { items: episodic, total: episodic.length },
    procedural: { items: procedural, total: procedural.length },
  };
}

/**
 * `GET /v1/memory` — agrupado por capa, o una sola rama con `?layer=`.
 * Espeja el aislamiento del backend de forma simplificada (el mock siempre
 * sirve el mismo dataset; el JWT real filtra por usuario).
 */
const VALID_LAYERS = new Set(["semantic", "episodic", "procedural"]);

/** Busca un ítem por capa + referencia (UUID en sem/epi, `key` en procedural). */
function findMemoryItem(layer: string, ref: string, now: Date) {
  const list = buildMemoryList(now);
  if (layer === "semantic") return list.semantic.items.find((i) => i.id === ref);
  if (layer === "episodic") return list.episodic.items.find((i) => i.id === ref);
  if (layer === "procedural") return list.procedural.items.find((i) => i.key === ref);
  return undefined;
}

const memoryNotFound = () =>
  HttpResponse.json({ detail: "memoria no encontrada" }, { status: 404 });

export const memoryHandlers = [
  http.get(apiUrl("/v1/memory"), ({ request }) => {
    const url = new URL(request.url);
    const layer = url.searchParams.get("layer");
    const list = buildMemoryList(new Date());

    if (layer === null) return HttpResponse.json(list);
    if (layer === "semantic" || layer === "episodic" || layer === "procedural") {
      return HttpResponse.json(list[layer]);
    }
    // El backend responde 422 a una capa inválida.
    return HttpResponse.json(
      { error: "validation", detail: "layer inválida", field: "layer" },
      { status: 422 },
    );
  }),

  // `GET /v1/memory/{layer}/{ref}` — detalle de un ítem. 422 capa inválida,
  // 404 ref inexistente (mismo 404 que una ajena: sin oráculo de existencia).
  http.get(apiUrl("/v1/memory/:layer/:ref"), ({ params }) => {
    const layer = String(params.layer);
    const ref = decodeURIComponent(String(params.ref));
    if (!VALID_LAYERS.has(layer)) {
      return HttpResponse.json(
        { error: "validation", detail: "layer inválida", field: "layer" },
        { status: 422 },
      );
    }
    const item = findMemoryItem(layer, ref, new Date());
    return item ? HttpResponse.json(item) : memoryNotFound();
  }),
];
