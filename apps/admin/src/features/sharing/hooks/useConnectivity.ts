"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { ConnectivityOut, type ConnectivityOutT } from "../schemas";

/**
 * Datos de `GET /v1/admin/connectivity` (Conexión / Compartir).
 *
 * Estado del tailnet + URLs para compartir. Igual que `useSystem`/`useServing`, NO
 * se segmenta por `range` (es una foto de conectividad, no una métrica de negocio):
 * `qk.admin.connectivity()` no lleva parámetro. El contrato Zod valida la respuesta
 * en el borde; en dev el fetch lo intercepta MSW (`connectivityFixture`).
 */
export function useConnectivity() {
  return useQuery<ConnectivityOutT>({
    queryKey: qk.admin.connectivity(),
    queryFn: async () => ConnectivityOut.parse(await api.get<unknown>("/v1/admin/connectivity")),
  });
}
