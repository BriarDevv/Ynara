"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminUsersOut, type AdminUsersOutT } from "@/features/users/schemas";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { useRangeStore } from "@/stores/range";

/**
 * Hook de datos de la pantalla F1.2 — Usuarios & Actividad (blueprint §3, §4.2).
 *
 * Lee el rango temporal global del `useRangeStore` (chrome de la topbar) y pega
 * a `GET /v1/admin/users?range=`. La respuesta cruda (`unknown`) se valida con
 * `AdminUsersOut.parse` ANTES de devolverse: el contrato Zod es la frontera de
 * confianza del panel, así que un shape inesperado del backend rompe acá (en el
 * `queryFn`) y no más adentro en el render. Los flags `isApproximate`/`isEstimate`
 * son `z.literal(true)`: si el backend olvidara rotular el proxy, el parse falla.
 *
 * En dev todo esto corre sobre MSW (`adminHandlers`), que ya parsea el fixture
 * con el mismo schema; cuando exista el endpoint real, el hook no cambia.
 *
 * @returns el resultado de `useQuery` tipado a `AdminUsersOutT`.
 */
export function useUsers() {
  const range = useRangeStore((s) => s.range);

  return useQuery<AdminUsersOutT>({
    queryKey: qk.admin.users(range),
    queryFn: async () => {
      const raw = await api.get<unknown>(`/v1/admin/users?range=${range}`);
      return AdminUsersOut.parse(raw);
    },
  });
}
