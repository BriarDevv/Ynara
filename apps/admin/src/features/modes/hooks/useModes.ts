"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminModesOut, type AdminModesOutT } from "@/features/modes/schemas";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { useRangeStore } from "@/stores/range";

/**
 * Hook de datos de la pantalla F1.3 — Modos (blueprint §3, §4.3).
 *
 * Lee el rango temporal global del `useRangeStore` (chrome de la topbar) y pega
 * a `GET /v1/admin/modes?range=`. La respuesta cruda (`unknown`) se valida con
 * `AdminModesOut.parse` ANTES de devolverse: el contrato Zod es la frontera de
 * confianza del panel, así que un shape inesperado del backend rompe acá (en el
 * `queryFn`) y no más adentro en el render.
 *
 * En dev todo esto corre sobre MSW (`adminHandlers`), que ya parsea el fixture
 * con el mismo schema; cuando exista el endpoint real, el hook no cambia.
 *
 * @returns el resultado de `useQuery` tipado a `AdminModesOutT`.
 */
export function useModes() {
  const range = useRangeStore((s) => s.range);

  return useQuery<AdminModesOutT>({
    queryKey: qk.admin.modes(range),
    queryFn: async () => {
      const raw = await api.get<unknown>(`/v1/admin/modes?range=${range}`);
      return AdminModesOut.parse(raw);
    },
  });
}
