import {
  type AgendaEvent,
  EventCreateSchema,
  EventPatchSchema,
  type EventsResponse,
} from "@ynara/shared-schemas";
import { startOfWeek } from "./format";

/**
 * Mock-first del dominio **Agenda** (mobile) — espejo de
 * `apps/web/src/features/agenda/mocks.ts`. No hay backend de `/v1/events`
 * todavía; la UI corre contra este mock tipado con los Zod de
 * `@ynara/shared-schemas`. Se inyecta en el cliente de core vía
 * `configureApi.fetchImpl` (ver `lib/api.ts`), encadenado entre Memoria y Hoy.
 *
 * Store **mutable y cacheado** (igual que Hoy / Memoria): crear, editar o
 * borrar un evento persiste durante la sesión, así el optimismo de los hooks
 * tiene contra qué reconciliar. No persiste fuera de la sesión.
 */

// ---------- Helpers Hermes-safe (copiados de memory/mocks.ts) ----------

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
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

// ---------- Seed de eventos demo ----------

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
 * día/semana se vean vivas: Clase de Sistemas / Gym / Reunión cátedra /
 * Bloque de tesis (tentative) / Cumple. Mismo seed que web.
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

// ---------- Contador de ID para eventos nuevos ----------

let _idCounter = 100;
function nextId(): string {
  _idCounter += 1;
  return `0193d0ff-0000-4000-8000-${String(_idCounter).padStart(12, "0")}`;
}

// ---------- Regex para rutas ----------

/** Matchea `/v1/events/<id>` (sin query). */
const EVENT_ID_RE = /\/v1\/events\/([^/?]+)$/;

/**
 * Handler del dominio Agenda. Devuelve `Response` si el path es de `/v1/events`,
 * o `null` si no (para que el dispatcher caiga al siguiente mock / fetch real).
 * Hermes-safe, no usa URLSearchParams. Core siempre pasa la URL como string ya resuelta.
 */
export function agendaMockResponse(input: string, init?: RequestInit): Response | null {
  const qIndex = input.indexOf("?");
  const path = qIndex >= 0 ? input.slice(0, qIndex) : input;
  const method = (init?.method ?? "GET").toUpperCase();

  // /v1/events/:id — PATCH y DELETE.
  const eventMatch = EVENT_ID_RE.exec(path);
  if (eventMatch) {
    const id = decodeURIComponent(eventMatch[1]);

    if (method === "PATCH") {
      const parsed = EventPatchSchema.safeParse(parseBody(init?.body));
      if (!parsed.success) {
        const first = parsed.error.issues[0];
        return json(
          {
            error: "validation",
            detail: first?.message ?? "body inválido",
            field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
          },
          422,
        );
      }
      const event = getStore().find((e) => e.id === id);
      if (!event) return json({ error: "not_found", detail: "evento inexistente" }, 404);
      Object.assign(event, parsed.data);
      return json(event);
    }

    if (method === "DELETE") {
      const list = getStore();
      const idx = list.findIndex((e) => e.id === id);
      if (idx === -1) return json({ error: "not_found", detail: "evento inexistente" }, 404);
      list.splice(idx, 1);
      return new Response(null, { status: 204 });
    }

    // Método no soportado en este path.
    return null;
  }

  // /v1/events — GET y POST. (La UI filtra por día/rango en cliente; el mock
  // ignora el query y devuelve la lista completa.)
  if (path.endsWith("/v1/events")) {
    if (method === "GET") {
      const items = getStore();
      const body: EventsResponse = { items, total: items.length };
      return json(body);
    }

    if (method === "POST") {
      const parsed = EventCreateSchema.safeParse(parseBody(init?.body));
      if (!parsed.success) {
        const first = parsed.error.issues[0];
        return json(
          {
            error: "validation",
            detail: first?.message ?? "body inválido",
            field: first?.path[0] !== undefined ? String(first.path[0]) : undefined,
          },
          422,
        );
      }
      const created: AgendaEvent = {
        id: nextId(),
        title: parsed.data.title,
        start_at: parsed.data.start_at,
        duration_min: parsed.data.duration_min,
        mode: parsed.data.mode ?? null,
        status: "confirmed",
        location: parsed.data.location ?? null,
      };
      getStore().push(created);
      return json(created, 201);
    }
  }

  // No es un endpoint de Agenda.
  return null;
}
