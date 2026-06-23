import type {
  EpisodicMemoryOut,
  MemoryList,
  MemorySearchHit,
  MemorySearchResponse,
  MemoryWipeConfirm,
  ProceduralMemoryOut,
  SemanticMemoryOut,
} from "@ynara/shared-schemas";
import { MemoryWipeConfirmSchema } from "@ynara/shared-schemas";
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
const MEMORY_IDS = {
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

const VALID_LAYERS = new Set(["semantic", "episodic", "procedural"]);

/**
 * Store mutable del mock. Se materializa una vez (fechado al primer acceso, así
 * el timeline no "salta" entre requests) y PATCH/DELETE lo mutan in-place, para
 * que la demo sea coherente: editar y volver muestra el cambio, borrar lo saca
 * de la lista. En el backend real esto vive en Postgres; un full reload resetea
 * el mock. NO persiste fuera de la sesión.
 */
let store: MemoryList | null = null;
function getStore(): MemoryList {
  if (store === null) store = buildMemoryList(new Date());
  return store;
}

/** Busca un ítem por capa + referencia (UUID en sem/epi, `key` en procedural). */
function findMemoryItem(layer: string, ref: string) {
  const list = getStore();
  if (layer === "semantic") return list.semantic.items.find((i) => i.id === ref);
  if (layer === "episodic") return list.episodic.items.find((i) => i.id === ref);
  if (layer === "procedural") return list.procedural.items.find((i) => i.key === ref);
  return undefined;
}

/**
 * Búsqueda PROVISIONAL (`GET /v1/memory/search`, endpoint todavía inexistente).
 * El store real hace embed + ANN + decrypt + rerank; el mock hace un match por
 * substring (case-insensitive) sobre el texto de cada ítem y asigna un score
 * decreciente, suficiente para construir la UI. Devuelve hasta cuantos matcheen,
 * ordenados por score.
 */
export function searchMemoryList(list: MemoryList, query: string): MemorySearchHit[] {
  const q = query.trim().toLowerCase();
  if (q.length === 0) return [];
  const hits: Omit<MemorySearchHit, "score">[] = [];

  for (const item of list.semantic.items) {
    if (item.content.toLowerCase().includes(q)) {
      hits.push({
        layer: "semantic",
        ref: item.id,
        snippet: item.content,
        occurred_at: item.created_at,
      });
    }
  }
  for (const item of list.episodic.items) {
    if (item.summary.toLowerCase().includes(q)) {
      hits.push({
        layer: "episodic",
        ref: item.id,
        snippet: item.summary,
        occurred_at: item.occurred_at,
      });
    }
  }
  for (const item of list.procedural.items) {
    const values = Object.values(item.value).join(" ");
    const haystack = `${item.key} ${values}`.toLowerCase();
    if (haystack.includes(q)) {
      const snippet = `${item.key.replace(/[_-]+/g, " ")}: ${Object.values(item.value).join(", ")}`;
      hits.push({
        layer: "procedural",
        ref: item.key,
        snippet,
        occurred_at: item.last_reinforced_at,
      });
    }
  }

  // Score decreciente por orden de aparición (mock determinista, 0..1).
  return hits.map((hit, i) => ({ ...hit, score: Math.max(0.5, 0.95 - i * 0.08) }));
}

const memoryNotFound = () =>
  HttpResponse.json({ detail: "memoria no encontrada" }, { status: 404 });

const invalidLayer = () =>
  HttpResponse.json(
    { error: "validation", detail: "layer inválida", field: "layer" },
    { status: 422 },
  );

export const memoryHandlers = [
  // `GET /v1/memory` — agrupado por capa, o una sola rama con `?layer=`.
  http.get(apiUrl("/v1/memory"), ({ request }) => {
    const url = new URL(request.url);
    const layer = url.searchParams.get("layer");
    const list = getStore();

    if (layer === null) return HttpResponse.json(list);
    if (layer === "semantic" || layer === "episodic" || layer === "procedural") {
      return HttpResponse.json(list[layer]);
    }
    return invalidLayer();
  }),

  // `GET /v1/memory/search?q=` — PROVISIONAL (endpoint todavía inexistente).
  // Va antes de `:layer/:ref` por claridad (no colisiona: `search` es 1 segmento).
  http.get(apiUrl("/v1/memory/search"), ({ request }) => {
    const q = new URL(request.url).searchParams.get("q") ?? "";
    const results = searchMemoryList(getStore(), q);
    const response: MemorySearchResponse = { query: q, total: results.length, results };
    return HttpResponse.json(response);
  }),

  // `GET /v1/memory/{layer}/{ref}` — detalle de un ítem. 422 capa inválida,
  // 404 ref inexistente (mismo 404 que una ajena: sin oráculo de existencia).
  http.get(apiUrl("/v1/memory/:layer/:ref"), ({ params }) => {
    const layer = String(params.layer);
    const ref = decodeURIComponent(String(params.ref));
    if (!VALID_LAYERS.has(layer)) return invalidLayer();
    const item = findMemoryItem(layer, ref);
    return item ? HttpResponse.json(item) : memoryNotFound();
  }),

  // `PATCH /v1/memory/{layer}/{ref}` — edita un ítem. semantic→content,
  // procedural→value; episodic devuelve 405 (el summary lo genera el worker).
  http.patch(apiUrl("/v1/memory/:layer/:ref"), async ({ params, request }) => {
    const layer = String(params.layer);
    const ref = decodeURIComponent(String(params.ref));
    if (!VALID_LAYERS.has(layer)) return invalidLayer();
    if (layer === "episodic") {
      return HttpResponse.json({ detail: "no se puede editar un episodio" }, { status: 405 });
    }

    const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
    const item = findMemoryItem(layer, ref);
    if (!item) return memoryNotFound();

    if (layer === "semantic") {
      const content = body?.content;
      if (typeof content !== "string" || content.length < 1 || content.length > 4096) {
        return HttpResponse.json(
          { error: "validation", detail: "content inválido", field: "content" },
          { status: 422 },
        );
      }
      Object.assign(item, { content, updated_at: new Date().toISOString() });
      return HttpResponse.json(item);
    }

    // procedural
    const value = body?.value;
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      return HttpResponse.json(
        { error: "validation", detail: "value inválido", field: "value" },
        { status: 422 },
      );
    }
    Object.assign(item, { value, updated_at: new Date().toISOString() });
    return HttpResponse.json(item);
  }),

  // `DELETE /v1/memory/{layer}/{ref}` — borra un ítem (las 3 capas). 204 sin body.
  http.delete(apiUrl("/v1/memory/:layer/:ref"), ({ params }) => {
    const layer = String(params.layer);
    const ref = decodeURIComponent(String(params.ref));
    if (!VALID_LAYERS.has(layer)) return invalidLayer();

    const list = getStore();
    let removed = false;
    if (layer === "semantic") {
      const i = list.semantic.items.findIndex((x) => x.id === ref);
      if (i !== -1) {
        list.semantic.items.splice(i, 1);
        list.semantic.total = list.semantic.items.length;
        removed = true;
      }
    } else if (layer === "episodic") {
      const i = list.episodic.items.findIndex((x) => x.id === ref);
      if (i !== -1) {
        list.episodic.items.splice(i, 1);
        list.episodic.total = list.episodic.items.length;
        removed = true;
      }
    } else {
      const i = list.procedural.items.findIndex((x) => x.key === ref);
      if (i !== -1) {
        list.procedural.items.splice(i, 1);
        list.procedural.total = list.procedural.items.length;
        removed = true;
      }
    }
    return removed ? new HttpResponse(null, { status: 204 }) : memoryNotFound();
  }),

  // `GET /v1/memory/export` — export versionado de las 3 capas completas
  // (descifradas, sin paginar). El shape sigue `MemoryExportSchema`.
  http.get(apiUrl("/v1/memory/export"), () => {
    const list = getStore();
    return HttpResponse.json({
      version: 1,
      exported_at: new Date().toISOString(),
      semantic: list.semantic.items,
      episodic: list.episodic.items,
      procedural: list.procedural.items,
    });
  }),

  // `POST /v1/memory/wipe` — preview (`?dry_run=true`) o execute.
  //
  // dry_run=true  → 200 con conteos actuales (lo que se borraría). No muta.
  // execute       → valida `expected_*`; si no coinciden con el recount →
  //                 409 con conteos actuales y NO borra nada (guarda de
  //                 intención, regla #3). Si coinciden → vacía las 3 capas.
  http.post(apiUrl("/v1/memory/wipe"), async ({ request }) => {
    const url = new URL(request.url);
    const isDryRun = url.searchParams.get("dry_run") === "true";
    const list = getStore();

    const semantic = list.semantic.items.length;
    const episodic = list.episodic.items.length;
    const procedural = list.procedural.items.length;
    const total = semantic + episodic + procedural;

    if (isDryRun) {
      return HttpResponse.json({ semantic, episodic, procedural, total });
    }

    // Execute: requiere body con los expected_* (guarda de intención).
    const json = await request.json().catch(() => null);
    const parsed = MemoryWipeConfirmSchema.safeParse(json);
    if (!parsed.success) {
      return HttpResponse.json(
        { error: "validation", detail: "body inválido: faltan o son inválidos expected_*" },
        { status: 422 },
      );
    }

    const { expected_semantic, expected_episodic, expected_procedural } =
      parsed.data as MemoryWipeConfirm;

    // Reconteo actual; si no coincide con los expected → 409, sin borrar nada.
    if (
      expected_semantic !== semantic ||
      expected_episodic !== episodic ||
      expected_procedural !== procedural
    ) {
      return HttpResponse.json(
        {
          message: "los conteos cambiaron, revisá de nuevo",
          semantic,
          episodic,
          procedural,
          total,
        },
        { status: 409 },
      );
    }

    // Coinciden → vaciar las 3 capas del store.
    list.semantic.items = [];
    list.semantic.total = 0;
    list.episodic.items = [];
    list.episodic.total = 0;
    list.procedural.items = [];
    list.procedural.total = 0;

    return HttpResponse.json({ semantic, episodic, procedural, total });
  }),
];
