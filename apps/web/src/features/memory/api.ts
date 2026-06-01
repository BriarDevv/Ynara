"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type MemoryItemOut,
  type MemoryLayer,
  MemoryListSchema,
  memoryOutSchemaFor,
  type ProceduralMemoryPatch,
  type SemanticMemoryPatch,
} from "@ynara/shared-schemas";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { entriesForLayer, relatedEntries, sessionRefOf, toTimelineEntries } from "./timeline";

/** El filtro activo del timeline: una capa puntual o todas. */
export type TimelineFilter = MemoryLayer | "all";

/** GET de la lista agrupada cruda. Compartido por timeline y relacionados. */
function fetchMemoryList() {
  return api.get<unknown>("/v1/memory").then((raw) => MemoryListSchema.parse(raw));
}

/**
 * Trae el timeline de memoria desde `GET /v1/memory` (real; en dev corre contra
 * el handler MSW que espeja el contrato). La validación Zod
 * (`@ynara/shared-schemas`) rechaza en cliente lo mismo que el backend, así un
 * contrato roto se ve en desarrollo, no en producción.
 *
 * Una sola query trae la lista agrupada completa y el filtro por capa se aplica
 * en `select` (client-side): los cambios de filtro son instantáneos (sin
 * refetch) y `useMemoryRelated` reusa exactamente la misma cache. Devuelve las
 * entradas ya ordenadas por fecha desc; el agrupado por bucket (que depende de
 * `now`) lo hace la vista para no fijar el tiempo en la query.
 */
export function useMemoryTimeline(filter: TimelineFilter) {
  return useQuery({
    queryKey: qk.memory.all(),
    queryFn: fetchMemoryList,
    select: (list) =>
      filter === "all" ? toTimelineEntries(list) : entriesForLayer(filter, list[filter].items),
  });
}

/**
 * Detalle de un ítem de memoria (`GET /v1/memory/{layer}/{ref}`). Parsea con el
 * schema `*Out` de la capa (el payload no trae discriminador embebido; la capa
 * la sabe el caller por la URL). Un 404 del backend (ref inexistente o ajena)
 * llega como `ApiError` con status 404, que la vista distingue de un error real.
 */
export function useMemoryDetail(layer: MemoryLayer, ref: string) {
  return useQuery({
    queryKey: qk.memory.detail(layer, ref),
    queryFn: async (): Promise<MemoryItemOut> => {
      const raw = await api.get<unknown>(`/v1/memory/${layer}/${encodeURIComponent(ref)}`);
      return memoryOutSchemaFor(layer).parse(raw);
    },
  });
}

/**
 * Memorias relacionadas con `item`: las que comparten su sesión de origen.
 * Derivación de cliente sobre la misma lista del timeline (no hay endpoint de
 * relacionados); reusa la cache de `qk.memory.all()` vía `select`. Para una
 * capa sin sesión (procedural) el resultado es vacío.
 */
export function useMemoryRelated(layer: MemoryLayer, item: MemoryItemOut | undefined) {
  const sessionId = item ? sessionRefOf(layer, item) : null;
  return useQuery({
    queryKey: qk.memory.all(),
    queryFn: fetchMemoryList,
    enabled: item !== undefined,
    select: (list) =>
      relatedEntries(list, { sessionId, excludeLayer: layer, excludeRef: refOf(layer, item) }),
  });
}

/** El identificador de detalle de un ítem (UUID o key). `""` si no hay item. */
function refOf(layer: MemoryLayer, item: MemoryItemOut | undefined): string {
  if (!item) return "";
  return layer === "procedural" && "key" in item ? item.key : "id" in item ? item.id : "";
}

/** Body del PATCH según la capa (semantic→content, procedural→value). */
export type MemoryPatch = SemanticMemoryPatch | ProceduralMemoryPatch;

/**
 * Edita un ítem (`PATCH /v1/memory/{layer}/{ref}`). Al confirmar, siembra el
 * detalle con el ítem actualizado e invalida `qk.memory.all()` (prefijo →
 * timeline + relacionados) para que la lista refleje el cambio. La capa
 * episódica no admite PATCH (el backend responde 405).
 */
export function usePatchMemory(layer: MemoryLayer, ref: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (patch: MemoryPatch): Promise<MemoryItemOut> => {
      const raw = await api.patch<unknown>(`/v1/memory/${layer}/${encodeURIComponent(ref)}`, patch);
      return memoryOutSchemaFor(layer).parse(raw);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(qk.memory.detail(layer, ref), updated);
      queryClient.invalidateQueries({ queryKey: qk.memory.all() });
    },
  });
}

/**
 * Borra un ítem (`DELETE /v1/memory/{layer}/{ref}`, 204 sin body). Limpia la
 * cache del detalle e invalida la lista. La navegación de vuelta a `/memoria`
 * la hace el componente (para poder confirmar primero).
 */
export function useDeleteMemory(layer: MemoryLayer, ref: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>(`/v1/memory/${layer}/${encodeURIComponent(ref)}`),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: qk.memory.detail(layer, ref) });
      queryClient.invalidateQueries({ queryKey: qk.memory.all() });
    },
  });
}
