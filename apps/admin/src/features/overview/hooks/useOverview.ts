"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminOverviewOut, type AdminOverviewOutT } from "@/features/overview/schemas";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import type { RangeId } from "@/stores/range";

/**
 * Hook de datos del Overview (blueprint §3 F1.1, §4.1).
 *
 * `GET /v1/admin/overview?range=` → valida la respuesta con el contrato Zod del
 * feature antes de entregarla a la UI. El `Schema.parse(await api.get<unknown>())`
 * es la frontera de confianza: el endpoint (o el handler MSW) puede mentir; el
 * panel solo consume lo que el contrato garantiza. Si el shape no cumple, el
 * error sube al `error.tsx` del grupo `(panel)`.
 *
 * La query key se segmenta por `range` (la ventana temporal global), así que
 * cambiar el segmented control del topbar dispara un refetch con su propia
 * entrada de cache. Invalidar `["admin"]` alcanza todas las vistas.
 */
export function useOverview(range: RangeId) {
  return useQuery<AdminOverviewOutT>({
    queryKey: qk.admin.overview(range),
    queryFn: async () =>
      AdminOverviewOut.parse(await api.get<unknown>(`/v1/admin/overview?range=${range}`)),
  });
}
