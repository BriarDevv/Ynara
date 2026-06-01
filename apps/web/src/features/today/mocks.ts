import {
  type ApiErrorBody,
  type Recap,
  type Suggestion,
  type SuggestionsResponse,
  type Task,
  TaskPatchSchema,
  type TasksResponse,
} from "@ynara/shared-schemas";
import { HttpResponse, http } from "msw";
import { env } from "@/lib/env";

/**
 * Handlers MSW del dashboard **Hoy** (build-plan Fase E) — **PROVISIONALES**:
 * el backend de tareas todavía no existe (track backend: `Task` model + CRUD,
 * gate regla #1). La UI se construye contra estos handlers tipados con los Zod
 * de `@ynara/shared-schemas`; cuando el endpoint real exista, se apaga el
 * handler y la UI queda sin tocar.
 *
 * El store es **mutable y cacheado** (como el de memoria) para que el toggle de
 * una prioridad persista durante la sesión: marcás una tarea hecha y al volver
 * a Hoy sigue hecha.
 */

const apiUrl = (path: string) => `${env.NEXT_PUBLIC_API_URL}${path}`;

function errorResponse(body: ApiErrorBody, status: number) {
  return HttpResponse.json(body, { status });
}

/** UUIDs estables de las prioridades demo (para que el toggle matchee por id). */
const TASK_IDS = {
  mail: "0193c001-0000-4000-8000-000000000001",
  llamada: "0193c001-0000-4000-8000-000000000002",
  briefs: "0193c001-0000-4000-8000-000000000003",
} as const;

/** Hoy a una hora puntual, como ISO (UTC). El display lo re-localiza el front. */
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

let suggestionsStore: Suggestion[] | null = null;

function getSuggestions(): Suggestion[] {
  if (!suggestionsStore) suggestionsStore = buildSuggestions();
  return suggestionsStore;
}

/**
 * Recap del día (wireframe 15). `pending: true` = el día no se cerró todavía
 * (por eso aparece el CTA en Hoy), pero Ynara ya tiene un borrador: el
 * `headline` y los `highlights` de lo que pasó. Cerrarlo de verdad (y
 * regenerarlo con el LLM) es la Fase H2 / backend.
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

export const todayHandlers = [
  // GET /v1/tasks — prioridades del día.
  http.get(apiUrl("/v1/tasks"), () => {
    const items = getStore();
    const body: TasksResponse = { items, total: items.length };
    return HttpResponse.json(body);
  }),

  // PATCH /v1/tasks/:id — toggle de estado (marcar hecha / re-abrir).
  http.patch(apiUrl("/v1/tasks/:id"), async ({ params, request }) => {
    const json = await request.json().catch(() => null);
    const parsed = TaskPatchSchema.safeParse(json);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      return errorResponse(
        {
          error: "validation",
          detail: first?.message ?? "body inválido",
          field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
        },
        422,
      );
    }
    const task = getStore().find((t) => t.id === params.id);
    if (!task) {
      return errorResponse({ error: "not_found", detail: "tarea inexistente" }, 404);
    }
    task.status = parsed.data.status;
    return HttpResponse.json(task);
  }),

  // GET /v1/suggestions — "Ynara sugiere".
  http.get(apiUrl("/v1/suggestions"), () => {
    const body: SuggestionsResponse = { items: getSuggestions() };
    return HttpResponse.json(body);
  }),

  // GET /v1/recap — recap del día (CTA del wireframe 06 → sheet 15).
  http.get(apiUrl("/v1/recap"), () => HttpResponse.json(buildRecap(new Date()))),
];
