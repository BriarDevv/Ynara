import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AdminAuditPage,
  type AdminAuditPageT,
  type AuditFilterState,
} from "@/features/audit/schemas";
import type { ApiError } from "@/lib/api";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import type { RangeId } from "@/stores/range";

/**
 * Tamaño de página por default de la tabla soberana. El backend acota con
 * `LIMIT`; el cliente lo refleja para que `total` (de la query CON filtros) y la
 * paginación `limit/offset` cuadren.
 */
export const AUDIT_PAGE_SIZE = 50;

/**
 * Serializa filtros + paginación a los query params de `/v1/admin/audit`
 * (blueprint §4.5). Cada filtro en `null` se omite (= "sin filtrar por ese
 * campo"); `sensitive` es tri-estado (`null`/`true`/`false`), por eso se chequea
 * contra `null` y no por truthiness. `range` siempre viaja.
 *
 * Pura y exportada para que el hook y los tests compartan la misma
 * serialización (evita drift entre lo que se cachea y lo que se pide).
 */
export function buildAuditQuery(
  range: RangeId,
  filters: AuditFilterState,
  page: number,
  pageSize: number = AUDIT_PAGE_SIZE,
): string {
  const sp = new URLSearchParams();
  sp.set("range", range);
  if (filters.operation) sp.set("operation", filters.operation);
  if (filters.targetLayer) sp.set("target_layer", filters.targetLayer);
  if (filters.originMode) sp.set("origin_mode", filters.originMode);
  if (filters.originModel) sp.set("origin_model", filters.originModel);
  if (filters.sensitive !== null) sp.set("sensitive", String(filters.sensitive));
  sp.set("limit", String(pageSize));
  sp.set("offset", String(page * pageSize));
  return sp.toString();
}

/**
 * Hook de la pantalla F1.5 — Audit Log soberano.
 *
 * `useQuery` clásico del panel: `queryKey` por `qk.admin.audit(range, filters,
 * page)` (cada combinación de filtros + página tiene su entrada de cache) y
 * `queryFn` que pega al endpoint y **re-parsea con el Zod** del feature. El
 * `.parse()` es la frontera de privacidad final: aunque el backend filtrara mal,
 * `record_hash`/`target_id` no existen en `AdminAuditRow` y nunca llegan al
 * cliente (regla #6, "vista soberana").
 *
 * `keepPreviousData` mantiene la página anterior visible mientras llega la nueva
 * (paginación/cambio de filtro sin parpadeo a vacío); `query.isPlaceholderData`
 * permite atenuar la tabla durante esa transición.
 *
 * @param range   Ventana temporal global (heredada del topbar).
 * @param filters Estado de los filtros de la tabla (`AuditFilters`).
 * @param page    Página 0-indexed.
 */
export function useAudit(range: RangeId, filters: AuditFilterState, page: number) {
  return useQuery<AdminAuditPageT, ApiError>({
    queryKey: qk.admin.audit(range, filters, page),
    queryFn: async () => {
      const raw = await api.get<unknown>(
        `/v1/admin/audit?${buildAuditQuery(range, filters, page)}`,
      );
      return AdminAuditPage.parse(raw);
    },
    placeholderData: keepPreviousData,
  });
}
