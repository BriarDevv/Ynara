"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type AgendaEvent,
  AgendaEventSchema,
  type EventCreate,
  type EventPatch,
  type EventsResponse,
  EventsResponseSchema,
} from "@ynara/shared-schemas";
import { api } from "../../api";
import { qk } from "../../query-keys";

/**
 * Hooks de data de **Agenda**, compartidos web + mobile (ADR-012). Validación
 * Zod en cliente: un contrato roto se ve en dev.
 *
 * PROVISIONAL: corren contra mocks (no hay backend de eventos todavía —
 * `/v1/events`). Cuando exista `CalendarEvent` + CRUD, estos hooks no cambian
 * (solo se apaga el handler mock). Las vistas día/semana filtran por día sobre
 * la lista del `useEvents`.
 */
export function useEvents() {
  return useQuery({
    queryKey: qk.agenda.all(),
    queryFn: async (): Promise<AgendaEvent[]> => {
      const raw = await api.get<unknown>("/v1/events");
      return EventsResponseSchema.parse(raw).items;
    },
  });
}

/** Crea un evento (`POST /v1/events`) e invalida la lista. */
export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (event: EventCreate): Promise<AgendaEvent> => {
      const raw = await api.post<unknown>("/v1/events", event);
      return AgendaEventSchema.parse(raw);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.agenda.all() });
    },
  });
}

/** Edita un evento (`PATCH /v1/events/{id}`, parcial) e invalida la lista. */
export function usePatchEvent(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (patch: EventPatch): Promise<AgendaEvent> => {
      const raw = await api.patch<unknown>(`/v1/events/${encodeURIComponent(id)}`, patch);
      return AgendaEventSchema.parse(raw);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.agenda.all() });
    },
  });
}

/** Borra un evento (`DELETE /v1/events/{id}`, 204) e invalida la lista. */
export function useDeleteEvent(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>(`/v1/events/${encodeURIComponent(id)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.agenda.all() });
    },
  });
}

/** Re-exporta los tipos del dominio para los componentes (evita imports cruzados). */
export type { AgendaEvent, EventCreate, EventPatch, EventsResponse };
