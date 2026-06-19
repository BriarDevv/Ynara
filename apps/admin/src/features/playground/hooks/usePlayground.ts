"use client";

import { useMutation } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api";
import { PlaygroundIn, type PlaygroundInT, PlaygroundOut, type PlaygroundOutT } from "../schemas";

/**
 * Completion ad-hoc del Playground (`POST /v1/admin/playground`, ADR-018 §2.2).
 *
 * **Sync, no SSE** (decisión de wire v1 del ADR): la mutation devuelve el turno
 * completo; el cursor pulsante de la UI vive solo durante `isPending`. Sin store
 * persistente, sin semántica de `Mode`, sin transporte de streaming: un
 * playground efímero de un turno. El body se valida con `PlaygroundIn` antes de
 * salir y la respuesta con `PlaygroundOut` en el borde (igual que las queries).
 *
 * Errores: `api.post` tira `ApiError` con el `status` del backend. Acá NO se
 * mapea a copy (eso es de UI) — se deja propagar para que el componente lo lea
 * vía `playgroundErrorCopy(error)` y muestre un mensaje NEUTRO por status,
 * espejo de la regla #4 server-side (el server ya manda `detail` sin payload).
 */
export function usePlayground() {
  return useMutation<PlaygroundOutT, unknown, PlaygroundInT>({
    mutationFn: async (input) => {
      const body = PlaygroundIn.parse(input);
      const raw = await api.post<unknown>("/v1/admin/playground", body);
      return PlaygroundOut.parse(raw);
    },
  });
}

/**
 * Copy NEUTRO por status para los fallos del playground (espejo de la regla #4:
 * nunca ecoamos el payload del error del modelo, solo un mensaje por código).
 * Cubre el mapeo del handler (§2.2 paso 7): 422 modelo/contexto, 409 fake, 503
 * caído/saturado, 504 timeout, 502 genérico; default para transporte/otros.
 */
export function playgroundErrorCopy(error: unknown): { title: string; hint: string } {
  const status = error instanceof ApiError ? error.status : 0;
  switch (status) {
    case 409:
      return {
        title: "Serving real no disponible.",
        hint: "El backend está en modo fake. Corré con LLM_BACKEND=vllm para generar.",
      };
    case 422:
      return {
        title: "El modelo rechazó la solicitud.",
        hint: "Revisá el modelo elegido o acortá el mensaje (puede exceder el contexto).",
      };
    case 503:
      return {
        title: "El serving no está disponible.",
        hint: "El modelo está caído o saturado. Reintentá en unos segundos.",
      };
    case 504:
      return {
        title: "La generación tardó demasiado.",
        hint: "Se agotó el timeout. Probá con menos tokens o el modo bajo rendimiento.",
      };
    case 502:
      return {
        title: "Error del serving.",
        hint: "El modelo respondió con un error. Reintentá la solicitud.",
      };
    default:
      return {
        title: "No pudimos contactar el serving.",
        hint: "Falló el transporte. Verificá la conexión y reintentá.",
      };
  }
}
