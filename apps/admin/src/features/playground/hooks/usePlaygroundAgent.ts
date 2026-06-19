"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  PlaygroundAgentOut,
  type PlaygroundAgentOutT,
  PlaygroundIn,
  type PlaygroundInT,
} from "../schemas";

/**
 * Turno en **modo agente** del Playground (`POST /v1/admin/playground/agent`,
 * Fase B / blueprint §4).
 *
 * Espejo de `usePlayground` (probe crudo) pero contra el endpoint del tool-loop
 * observado: el server corre `run_tool_loop` con el `default_registry()` de stubs
 * (`not_wired`, cero efecto real) y devuelve la respuesta + la traza de tools en
 * `actions`. **Sync, no SSE** (misma decisión de wire que el probe crudo): la
 * mutation devuelve el turno completo; el cursor pulsante vive solo en `isPending`.
 *
 * El body se valida con `PlaygroundIn` (mismo contrato de entrada que el probe) y
 * la respuesta con `PlaygroundAgentOut` en el borde, igual que el resto del panel.
 * Los errores propagan `ApiError` y se mapean a copy neutro vía la
 * `playgroundErrorCopy` compartida (regla #4: nunca ecoamos el payload del error).
 */
export function usePlaygroundAgent() {
  return useMutation<PlaygroundAgentOutT, unknown, PlaygroundInT>({
    mutationFn: async (input) => {
      const body = PlaygroundIn.parse(input);
      const raw = await api.post<unknown>("/v1/admin/playground/agent", body);
      return PlaygroundAgentOut.parse(raw);
    },
  });
}
