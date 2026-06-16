import type {
  EpisodicMemoryOut,
  MemoryList,
  MemorySearchHit,
  MemorySearchResponse,
  ProceduralMemoryOut,
  SemanticMemoryOut,
} from "@ynara/shared-schemas";

/**
 * Mock-first de **Memoria** (mobile) — espejo de
 * `apps/web/src/features/memory/mocks.ts`. List y detail SÍ existen en el backend
 * real (`/v1/memory`); search es provisional. El mock permite construir la UI sin
 * levantar Postgres: se inyecta en el cliente de core vía `configureApi.fetchImpl`
 * (ver `lib/api.ts`), encadenado con el mock de Hoy.
 *
 * Store **mutable y cacheado** (fechado al primer acceso, así el timeline no
 * "salta" entre requests): PATCH/DELETE lo mutan in-place para que la demo sea
 * coherente. No persiste fuera de la sesión.
 */

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

let store: MemoryList | null = null;
function getStore(): MemoryList {
  if (store === null) store = buildMemoryList(new Date());
  return store;
}

const VALID_LAYERS = new Set(["semantic", "episodic", "procedural"]);

/** Busca un ítem por capa + referencia (UUID en sem/epi, `key` en procedural). */
function findMemoryItem(layer: string, ref: string) {
  const list = getStore();
  if (layer === "semantic") return list.semantic.items.find((i) => i.id === ref);
  if (layer === "episodic") return list.episodic.items.find((i) => i.id === ref);
  if (layer === "procedural") return list.procedural.items.find((i) => i.key === ref);
  return undefined;
}

/**
 * Búsqueda PROVISIONAL (endpoint todavía inexistente): match por substring
 * (case-insensitive) sobre el texto de cada ítem, con score decreciente.
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

  return hits.map((hit, i) => ({ ...hit, score: Math.max(0.5, 0.95 - i * 0.08) }));
}

// ---------- Mock-fetch (Response | null; null = no es un path de memoria) ----------

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Lee un query param sin depender de URLSearchParams (Hermes-safe). */
function getParam(query: string, key: string): string | null {
  for (const pair of query.split("&")) {
    const eq = pair.indexOf("=");
    const k = eq >= 0 ? pair.slice(0, eq) : pair;
    if (k === key) return decodeURIComponent(eq >= 0 ? pair.slice(eq + 1) : "");
  }
  return null;
}

function parseBody(body: RequestInit["body"]): Record<string, unknown> | null {
  if (typeof body !== "string") return null;
  try {
    const parsed = JSON.parse(body);
    return typeof parsed === "object" && parsed !== null
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

const invalidLayer = () =>
  json({ error: "validation", detail: "layer inválida", field: "layer" }, 422);
const notFound = () => json({ detail: "memoria no encontrada" }, 404);

const DETAIL_RE = /\/v1\/memory\/([^/?]+)\/([^/?]+)$/;

/**
 * Handler del dominio Memoria. Devuelve `Response` si el path es de memoria, o
 * `null` si no (para que el dispatcher caiga al siguiente mock / fetch real).
 * Core siempre pasa la URL como string ya resuelta.
 */
export function memoryMockResponse(input: string, init?: RequestInit): Response | null {
  const qIndex = input.indexOf("?");
  const path = qIndex >= 0 ? input.slice(0, qIndex) : input;
  const query = qIndex >= 0 ? input.slice(qIndex + 1) : "";
  const method = (init?.method ?? "GET").toUpperCase();

  // GET /v1/memory/search?q= — PROVISIONAL.
  if (method === "GET" && path.endsWith("/v1/memory/search")) {
    const q = getParam(query, "q") ?? "";
    const results = searchMemoryList(getStore(), q);
    const body: MemorySearchResponse = { query: q, total: results.length, results };
    return json(body);
  }

  // /v1/memory/{layer}/{ref} — detalle (GET) / editar (PATCH) / borrar (DELETE).
  const match = DETAIL_RE.exec(path);
  if (match) {
    const layer = match[1];
    const ref = decodeURIComponent(match[2]);
    if (!VALID_LAYERS.has(layer)) return invalidLayer();

    if (method === "GET") {
      const item = findMemoryItem(layer, ref);
      return item ? json(item) : notFound();
    }

    if (method === "PATCH") {
      if (layer === "episodic") return json({ detail: "no se puede editar un episodio" }, 405);
      const item = findMemoryItem(layer, ref);
      if (!item) return notFound();
      const body = parseBody(init?.body);
      if (layer === "semantic") {
        const content = body?.content;
        if (typeof content !== "string" || content.length < 1 || content.length > 4096) {
          return json({ error: "validation", detail: "content inválido", field: "content" }, 422);
        }
        Object.assign(item, { content, updated_at: new Date().toISOString() });
        return json(item);
      }
      const value = body?.value;
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        return json({ error: "validation", detail: "value inválido", field: "value" }, 422);
      }
      Object.assign(item, { value, updated_at: new Date().toISOString() });
      return json(item);
    }

    if (method === "DELETE") {
      const list = getStore();
      const branch =
        layer === "semantic"
          ? list.semantic
          : layer === "episodic"
            ? list.episodic
            : list.procedural;
      const idx = branch.items.findIndex((x) => ("key" in x ? x.key : x.id) === ref);
      if (idx === -1) return notFound();
      branch.items.splice(idx, 1);
      branch.total = branch.items.length;
      return new Response(null, { status: 204 });
    }
  }

  // GET /v1/memory (+ ?layer=) — lista agrupada o una sola rama.
  if (method === "GET" && path.endsWith("/v1/memory")) {
    const list = getStore();
    const layer = getParam(query, "layer");
    if (layer === null) return json(list);
    if (layer === "semantic" || layer === "episodic" || layer === "procedural") {
      return json(list[layer]);
    }
    return invalidLayer();
  }

  return null;
}
