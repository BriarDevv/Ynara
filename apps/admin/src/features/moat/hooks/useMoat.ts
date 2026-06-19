"use client";

import { useQuery } from "@tanstack/react-query";
import { AdminMoatOut, type AdminMoatOutT } from "@/features/moat/schemas";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import type { RangeId } from "@/stores/range";

/**
 * `useMoat(range)` — datos de la pantalla F1.4 (Salud del Moat).
 *
 * Patrón canónico de los hooks del panel (blueprint §6): `useQuery` con la key
 * jerárquica `qk.admin.moat(range)` + `queryFn` que pega al endpoint y **valida
 * el shape con Zod en el borde** (`Schema.parse(await api.get<unknown>(...))`).
 * Si el backend devolviera un shape inesperado, el parse tira acá y no se
 * propaga data sucia a la UI (defensa de contrato, no solo de tipo).
 *
 * En dev el request lo intercepta MSW (`fixtures/handlers.ts` → `moatFixture`),
 * así la pantalla es navegable 100% sin backend. El `range` viaja como query
 * param y entra en la cache key: cambiar de ventana refetchea con su entrada
 * propia.
 *
 * Privacidad (regla #6): el contrato `AdminMoatOut` jamás trae contenido
 * descifrado — solo counts, deltas, series y metadata de `recentEpisodic`
 * (id + timestamp + flag de sensible).
 */
export function useMoat(range: RangeId) {
  return useQuery<AdminMoatOutT>({
    queryKey: qk.admin.moat(range),
    queryFn: async () =>
      AdminMoatOut.parse(await api.get<unknown>(`/v1/admin/moat?range=${range}`)),
  });
}
