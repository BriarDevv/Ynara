"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type Recap,
  RecapSchema,
  type Suggestion,
  SuggestionsResponseSchema,
  type Task,
  TaskSchema,
  type TaskStatus,
  type TasksResponse,
  TasksResponseSchema,
} from "@ynara/shared-schemas";
import { ApiError, api } from "../../api";
import { qk } from "../../query-keys";

/**
 * Hooks de data de "Hoy", compartidos web + mobile (ADR-012). Validación Zod
 * en cliente: un contrato roto se ve en dev.
 *
 * `/v1/tasks` ya existe en el backend (Tanda 1). `/v1/suggestions` y
 * `/v1/recap` NO están implementados todavía (decisión de producto, roadmap
 * D2/F); sus hooks degradan limpio ante un 404 para que Hoy renderice sin
 * bloqueos mientras esos endpoints no existan.
 */

/**
 * Helper de degradación graceful para endpoints no implementados aún.
 * Convierte un 404 (endpoint inexistente por diseño) en el valor `fallback`
 * en vez de propagar error. Otros errores (5xx, red, 401…) siguen propagando
 * para que react-query los trate como error real y el usuario pueda reintentar.
 */
async function notImplementedOr<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return fallback;
    throw err;
  }
}

export function useTasks() {
  return useQuery({
    queryKey: qk.today.tasks(),
    queryFn: async (): Promise<Task[]> => {
      const raw = await api.get<unknown>("/v1/tasks");
      return TasksResponseSchema.parse(raw).items;
    },
  });
}

export function useSuggestions() {
  return useQuery({
    queryKey: qk.today.suggestions(),
    queryFn: (): Promise<Suggestion[]> =>
      notImplementedOr(
        api
          .get<unknown>("/v1/suggestions")
          .then((raw) => SuggestionsResponseSchema.parse(raw).items),
        [],
      ),
  });
}

export function useRecap() {
  return useQuery({
    queryKey: qk.today.recap(),
    queryFn: (): Promise<Recap | undefined> =>
      notImplementedOr(
        api.get<unknown>("/v1/recap").then((raw) => RecapSchema.parse(raw)),
        undefined,
      ),
  });
}

/** El estado opuesto: el check togglea pending↔done. */
function flip(status: TaskStatus): TaskStatus {
  return status === "done" ? "pending" : "done";
}

/**
 * Togglea el estado de una prioridad (`PATCH /v1/tasks/{id}`) con update
 * optimista: el check responde al toque al instante y, si el request falla, se
 * revierte. `onSettled` re-sincroniza con el server por las dudas.
 */
export function useToggleTask() {
  const queryClient = useQueryClient();
  const key = qk.today.tasks();
  return useMutation({
    mutationFn: async (task: Task): Promise<Task> => {
      const raw = await api.patch<unknown>(`/v1/tasks/${task.id}`, { status: flip(task.status) });
      return TaskSchema.parse(raw);
    },
    onMutate: async (task: Task) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Task[]>(key);
      queryClient.setQueryData<Task[]>(key, (curr) =>
        curr?.map((t) => (t.id === task.id ? { ...t, status: flip(t.status) } : t)),
      );
      return { previous };
    },
    onError: (_err, _task, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: key });
    },
  });
}

/** Re-exporta los tipos del cache para los componentes (evita imports cruzados). */
export type { Recap, Suggestion, Task, TasksResponse };
