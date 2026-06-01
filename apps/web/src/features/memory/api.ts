"use client";

import { useQuery } from "@tanstack/react-query";
import {
  EpisodicMemoryPageSchema,
  type MemoryLayer,
  MemoryListSchema,
  ProceduralMemoryPageSchema,
  SemanticMemoryPageSchema,
} from "@ynara/shared-schemas";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { entriesForLayer, type TimelineEntry, toTimelineEntries } from "./timeline";

/** El filtro activo del timeline: una capa puntual o todas. */
export type TimelineFilter = MemoryLayer | "all";

const PAGE_SCHEMA_BY_LAYER = {
  semantic: SemanticMemoryPageSchema,
  episodic: EpisodicMemoryPageSchema,
  procedural: ProceduralMemoryPageSchema,
} as const;

/**
 * Trae el timeline de memoria desde `GET /v1/memory` (real; en dev corre contra
 * el handler MSW que espeja el contrato). Sin filtro pega al endpoint agrupado
 * y aplana las 3 capas; con filtro pasa `?layer=` y normaliza esa rama. La
 * validación Zod (`@ynara/shared-schemas`) rechaza en cliente lo mismo que el
 * backend, así un contrato roto se ve en desarrollo, no en producción.
 *
 * Devuelve las entradas ya ordenadas por fecha desc; el agrupado por bucket
 * (que depende de `now`) lo hace la vista para no fijar el tiempo en la query.
 */
export function useMemoryTimeline(filter: TimelineFilter) {
  return useQuery({
    queryKey: filter === "all" ? qk.memory.all() : qk.memory.all({ layer: filter }),
    queryFn: async (): Promise<TimelineEntry[]> => {
      if (filter === "all") {
        const raw = await api.get<unknown>("/v1/memory");
        return toTimelineEntries(MemoryListSchema.parse(raw));
      }
      const raw = await api.get<unknown>(`/v1/memory?layer=${filter}`);
      const page = PAGE_SCHEMA_BY_LAYER[filter].parse(raw);
      return entriesForLayer(filter, page.items);
    },
  });
}
