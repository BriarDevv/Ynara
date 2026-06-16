import {
  type Recap,
  type Suggestion,
  type SuggestionsResponse,
  type Task,
  TaskPatchSchema,
  type TasksResponse,
} from "@ynara/shared-schemas";

/**
 * Mock-first del dashboard **Hoy** (mobile) — espejo de
 * `apps/web/src/features/today/mocks.ts`. El backend de tareas todavía no existe
 * (`/v1/tasks`, `/v1/suggestions`, `/v1/recap`), así que la UI corre contra este
 * mock tipado con los Zod de `@ynara/shared-schemas`; cuando el endpoint real
 * exista, se apaga el flag (`EXPO_PUBLIC_ENABLE_MOCKS`) y la UI queda sin tocar.
 *
 * A diferencia de web (MSW intercepta el `fetch` global del browser), acá el
 * `todayMockFetch` se inyecta en el cliente de core vía `configureApi.fetchImpl`
 * (ver `lib/api.ts`): intercepta los paths de Hoy y delega el resto —auth
 * incluido— al `fetch` real.
 *
 * El store de tareas es **mutable y cacheado** para que el check optimista
 * persista durante la sesión: marcás una tarea hecha y al volver a Hoy sigue
 * hecha.
 */

// ---------- Prioridades del día (`GET /v1/tasks`) ----------

/** UUIDs estables de las prioridades demo (para que el toggle matchee por id). */
const TASK_IDS = {
  mail: "0193c001-0000-4000-8000-000000000001",
  llamada: "0193c001-0000-4000-8000-000000000002",
  briefs: "0193c001-0000-4000-8000-000000000003",
} as const;

/** Hoy a una hora puntual, como ISO. El display lo re-localiza `format.ts`. */
function atToday(now: Date, hour: number, minute: number): string {
  const d = new Date(now);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

/**
 * Prioridades demo, fechadas relativo a `now` para que el header y las metas se
 * vean vivas. Espeja el wireframe 06: una hecha temprano + dos pendientes.
 */
export function buildTasks(now: Date): Task[] {
  return [
    {
      id: TASK_IDS.mail,
      title: "Responder mail de Takeshi",
      status: "done",
      scheduled_at: atToday(now, 9, 15),
      duration_min: null,
    },
    {
      id: TASK_IDS.llamada,
      title: "Llamada con equipo de diseño",
      status: "pending",
      scheduled_at: atToday(now, 14, 0),
      duration_min: 45,
    },
    {
      id: TASK_IDS.briefs,
      title: "Revisar briefs de la semana",
      status: "pending",
      scheduled_at: atToday(now, 16, 30),
      duration_min: 30,
    },
  ];
}

let store: Task[] | null = null;

/** Store mutable cacheado: seedea una sola vez y persiste toggles en la sesión. */
function getStore(): Task[] {
  if (!store) store = buildTasks(new Date());
  return store;
}

// ---------- Sugerencias (`GET /v1/suggestions`) ----------

/** UUIDs estables de las sugerencias demo. */
const SUGGESTION_IDS = {
  foco: "0193c002-0000-4000-8000-000000000001",
  pausa: "0193c002-0000-4000-8000-000000000002",
  reunion: "0193c002-0000-4000-8000-000000000003",
} as const;

/**
 * Sugerencias demo ("Ynara sugiere", wireframe 06/07). Cada una con su
 * **porqué** y el modo que la tinta. Read-only (las genera el LLM real a
 * futuro), así que no necesitan store mutable.
 */
export function buildSuggestions(): Suggestion[] {
  return [
    {
      id: SUGGESTION_IDS.foco,
      title: "Bloque de foco 10:30–12:00",
      why: "90 min sin notificaciones para la propuesta Õmi",
      mode: "productividad",
    },
    {
      id: SUGGESTION_IDS.pausa,
      title: "Pausá 10 min · estirá",
      why: "Llevás 90 min en pantalla",
      mode: "bienestar",
    },
    {
      id: SUGGESTION_IDS.reunion,
      title: "Preparar reunión 16:30",
      why: "Los briefs ya están cargados en el chat",
      mode: "productividad",
    },
  ];
}

// ---------- Recap del día (`GET /v1/recap`) ----------

/**
 * Recap del día (wireframe 15). `pending: true` = el día no se cerró todavía
 * (por eso aparece el CTA en Hoy), pero Ynara ya tiene un borrador: el
 * `headline` y los `highlights`. Cerrarlo de verdad (regenerar con el LLM) es
 * fase de backend.
 */
export function buildRecap(now: Date): Recap {
  return {
    pending: true,
    date: now.toISOString(),
    headline: "Un día de foco, con un pendiente que quedó para mañana.",
    highlights: [
      "Cerraste el mail de Takeshi temprano",
      "90 min de foco sin cortes en la propuesta Õmi",
      "Quedó pendiente revisar los briefs de la semana",
    ],
  };
}

// ---------- Mock-fetch (inyectado en core vía configureApi.fetchImpl) ----------

/** Respuesta JSON canned con el shape que espera el cliente de core. */
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Parsea el body (core ya lo serializó a string) de forma tolerante. */
function parseBody(body: RequestInit["body"]): unknown {
  if (typeof body !== "string") return null;
  try {
    return JSON.parse(body);
  } catch {
    return null;
  }
}

/** Matchea `/v1/tasks/<id>` (sin query) para el PATCH del toggle. */
const TASK_ID_RE = /\/v1\/tasks\/([^/?]+)$/;

/**
 * Mock-fetch del dominio Hoy: intercepta `/v1/tasks` (+ PATCH por id),
 * `/v1/suggestions` y `/v1/recap`; cualquier otra URL (auth, etc.) cae al
 * `fetch` real. Mismo contrato que `fetch` para enchufarse como `fetchImpl`
 * (core siempre pasa la URL como string ya resuelta).
 */
export async function todayMockFetch(input: string, init?: RequestInit): Promise<Response> {
  const path = input.split("?")[0];
  const method = (init?.method ?? "GET").toUpperCase();

  // PATCH /v1/tasks/:id — toggle de estado (marcar hecha / re-abrir).
  const taskMatch = method === "PATCH" ? TASK_ID_RE.exec(path) : null;
  if (taskMatch) {
    const parsed = TaskPatchSchema.safeParse(parseBody(init?.body));
    if (!parsed.success) {
      return json(
        { error: "validation", detail: parsed.error.issues[0]?.message ?? "body inválido" },
        422,
      );
    }
    const task = getStore().find((t) => t.id === taskMatch[1]);
    if (!task) return json({ error: "not_found", detail: "tarea inexistente" }, 404);
    task.status = parsed.data.status;
    return json(task);
  }

  // GET /v1/tasks — prioridades del día.
  if (method === "GET" && path.endsWith("/v1/tasks")) {
    const items = getStore();
    const body: TasksResponse = { items, total: items.length };
    return json(body);
  }

  // GET /v1/suggestions — "Ynara sugiere".
  if (method === "GET" && path.endsWith("/v1/suggestions")) {
    const body: SuggestionsResponse = { items: buildSuggestions() };
    return json(body);
  }

  // GET /v1/recap — recap del día.
  if (method === "GET" && path.endsWith("/v1/recap")) {
    return json(buildRecap(new Date()));
  }

  // No es un endpoint de Hoy → fetch real.
  return fetch(input, init);
}
