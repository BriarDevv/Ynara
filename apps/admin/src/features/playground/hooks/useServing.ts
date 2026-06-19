"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { ServingOut, type ServingOutT } from "../schemas";

/**
 * Datos de `GET /v1/admin/serving` (ADR-018 F1, contrato §2.1).
 *
 * Estado read-only del serving: backend (fake/vllm), salud agregada, y el
 * catálogo de modelos con sus served_names/role/quant/healthy. Igual que
 * `useSystem`, NO se segmenta por `range`: es una foto de runtime/config, no una
 * métrica de negocio (por eso `qk.admin.playground()` no lleva parámetro).
 *
 * El contrato Zod (`ServingOut`) valida la respuesta en el borde —y omite todo
 * secreto (sin `base_url`, regla #4)—: si el backend manda un shape inesperado,
 * falla acá y no en el render. En dev el fetch lo intercepta MSW
 * (`servingFixture`), que ya parsea su propio fixture contra este mismo schema.
 */
export function useServing() {
  return useQuery<ServingOutT>({
    queryKey: qk.admin.playground(),
    queryFn: async () => ServingOut.parse(await api.get<unknown>("/v1/admin/serving")),
  });
}
