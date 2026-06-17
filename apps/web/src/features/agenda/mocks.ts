import {
  type AgendaEvent,
  type ApiErrorBody,
  EventCreateSchema,
  EventPatchSchema,
  type EventsResponse,
} from "@ynara/shared-schemas";
import { HttpResponse, http } from "msw";
import { env } from "@/lib/env";
import { startOfWeek } from "./format";

/**
 * Handlers MSW de la **Agenda** (build-plan Fase F) — **PROVISIONALES**: no hay
 * backend de eventos todavía (track backend: `CalendarEvent` model + CRUD
 * `/v1/events`, gate regla #1 + decisión modelo propio). La UI día/semana corre
 * contra estos handlers tipados con los Zod de `@ynara/shared-schemas`; cuando
 * el endpoint real exista, se apaga el handler y la UI queda sin tocar.
 *
 * El store es **mutable y cacheado** (como Hoy / memoria): crear, editar o
 * borrar un evento persiste durante la sesión, así el optimismo de los hooks
 * tiene contra qué reconciliar.
 */

const apiUrl = (path: string) => `${env.NEXT_PUBLIC_API_URL}${path}`;

function errorResponse(body: ApiErrorBody, status: number) {
  return HttpResponse.json(body, { status });
}

function validationError(issues: ReadonlyArray<{ message: string; path: PropertyKey[] }>) {
  const first = issues[0];
  return errorResponse(
    {
      error: "validation",
      detail: first?.message ?? "body inválido",
      field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
    },
    422,
  );
}

/** UUIDs estables de los eventos demo (para que patch/delete matcheen por id). */
const EVENT_IDS = {
  sistemas: "0193d001-0000-4000-8000-000000000001",
  gym: "0193d001-0000-4000-8000-000000000002",
  catedra: "0193d001-0000-4000-8000-000000000003",
  tesis: "0193d001-0000-4000-8000-000000000004",
  cumple: "0193d001-0000-4000-8000-000000000005",
} as const;

/** ISO (UTC) del día `dayOffset` (0 = lunes) a las `hour:minute` locales de la semana de `now`. */
function atWeekDay(now: Date, dayOffset: number, hour: number, minute: number): string {
  const d = startOfWeek(now);
  d.setDate(d.getDate() + dayOffset);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

/**
 * Eventos demo, fechados relativo a la semana de `now` para que las vistas
 * día/semana se vean vivas (wireframes 10/11): un par de bloques de estudio, uno
 * de bienestar, una reunión y algo de la vida. Mezcla de modos y un `tentative`.
 */
export function buildEvents(now: Date): AgendaEvent[] {
  return [
    {
      id: EVENT_IDS.sistemas,
      title: "Clase de Sistemas",
      start_at: atWeekDay(now, 0, 10, 0),
      duration_min: 90,
      mode: "estudio",
      status: "confirmed",
      location: "Aula Magna",
    },
    {
      id: EVENT_IDS.gym,
      title: "Gym",
      start_at: atWeekDay(now, 0, 18, 30),
      duration_min: 60,
      mode: "bienestar",
      status: "confirmed",
      location: null,
    },
    {
      id: EVENT_IDS.catedra,
      title: "Reunión con cátedra",
      start_at: atWeekDay(now, 2, 16, 0),
      duration_min: 45,
      mode: "productividad",
      status: "confirmed",
      location: "Aula 3",
    },
    {
      id: EVENT_IDS.tesis,
      title: "Bloque de tesis",
      start_at: atWeekDay(now, 3, 9, 0),
      duration_min: 120,
      mode: "estudio",
      status: "tentative",
      location: null,
    },
    {
      id: EVENT_IDS.cumple,
      title: "Cumple de Caro",
      start_at: atWeekDay(now, 5, 21, 0),
      duration_min: 180,
      mode: "vida",
      status: "confirmed",
      location: "Casa de Caro",
    },
  ];
}

let store: AgendaEvent[] | null = null;

/** Store mutable cacheado: seedea una sola vez y persiste mutaciones en la sesión. */
function getStore(): AgendaEvent[] {
  if (!store) store = buildEvents(new Date());
  return store;
}

export const agendaHandlers = [
  // GET /v1/events — eventos de la semana (la UI filtra por día/rango).
  http.get(apiUrl("/v1/events"), () => {
    const items = getStore();
    const body: EventsResponse = { items, total: items.length };
    return HttpResponse.json(body);
  }),

  // POST /v1/events — crear. `status` arranca "confirmed"; mode/location → null por default.
  http.post(apiUrl("/v1/events"), async ({ request }) => {
    const json = await request.json().catch(() => null);
    const parsed = EventCreateSchema.safeParse(json);
    if (!parsed.success) return validationError(parsed.error.issues);
    const created: AgendaEvent = {
      id: crypto.randomUUID(),
      title: parsed.data.title,
      start_at: parsed.data.start_at,
      duration_min: parsed.data.duration_min,
      mode: parsed.data.mode ?? null,
      status: "confirmed",
      location: parsed.data.location ?? null,
    };
    getStore().push(created);
    return HttpResponse.json(created, { status: 201 });
  }),

  // PATCH /v1/events/:id — editar (parcial). Los campos no enviados quedan intactos.
  http.patch(apiUrl("/v1/events/:id"), async ({ params, request }) => {
    const json = await request.json().catch(() => null);
    const parsed = EventPatchSchema.safeParse(json);
    if (!parsed.success) return validationError(parsed.error.issues);
    const event = getStore().find((e) => e.id === params.id);
    if (!event) {
      return errorResponse({ error: "not_found", detail: "evento inexistente" }, 404);
    }
    Object.assign(event, parsed.data);
    return HttpResponse.json(event);
  }),

  // DELETE /v1/events/:id — borrar (204).
  http.delete(apiUrl("/v1/events/:id"), ({ params }) => {
    const list = getStore();
    const idx = list.findIndex((e) => e.id === params.id);
    if (idx === -1) {
      return errorResponse({ error: "not_found", detail: "evento inexistente" }, 404);
    }
    list.splice(idx, 1);
    return new HttpResponse(null, { status: 204 });
  }),
];
