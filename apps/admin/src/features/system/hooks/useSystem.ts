"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { AdminSystemOut, type AdminSystemOutT } from "../schemas";

/**
 * Datos de `GET /v1/admin/system` (blueprint §3 F1.6, contrato §4.6).
 *
 * A diferencia del resto del panel, NO se segmenta por `range`: es una foto de
 * runtime/config (guard anti-prod, estado de Postgres/Redis, inventario), no una
 * métrica de negocio con ventana temporal. Por eso la query key (`qk.admin.system`)
 * y el endpoint no llevan parámetro.
 *
 * El contrato Zod (`AdminSystemOut`) valida la respuesta en el borde: si el
 * backend manda un shape inesperado, falla acá y no en el render. En dev el
 * fetch lo intercepta MSW (`systemFixture`), que ya parsea su propio fixture
 * contra este mismo schema.
 */
export function useSystem() {
  return useQuery<AdminSystemOutT>({
    queryKey: qk.admin.system(),
    queryFn: async () => AdminSystemOut.parse(await api.get<unknown>("/v1/admin/system")),
  });
}
