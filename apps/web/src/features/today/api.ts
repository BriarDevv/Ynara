"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type Suggestion,
  SuggestionsResponseSchema,
  type Task,
  TaskSchema,
  type TaskStatus,
  type TasksResponse,
  TasksResponseSchema,
} from "@ynara/shared-schemas";
import { api } from "@/lib/api";
import { qk } from "@/lib/queryKeys";

/**
 * Prioridades del día (`GET /v1/tasks`). **PROVISIONAL**: corre contra el
 * handler MSW (no hay backend de tareas todavía). Validación Zod en cliente:
 * un contrato roto se ve en dev. Devuelve los ítems ya en orden del backend.
 */
export function useTasks() {
  return useQuery({
    queryKey: qk.today.tasks(),
    queryFn: async (): Promise<Task[]> => {
      const raw = await api.get<unknown>("/v1/tasks");
      return TasksResponseSchema.parse(raw).items;
    },
  });
}

/**
 * Sugerencias proactivas (`GET /v1/suggestions`). **PROVISIONAL**: corre contra
 * el handler MSW (las genera el LLM real a futuro). Devuelve los ítems crudos;
 * la sección decide cómo mostrarlos.
 */
export function useSuggestions() {
  return useQuery({
    queryKey: qk.today.suggestions(),
    queryFn: async (): Promise<Suggestion[]> => {
      const raw = await api.get<unknown>("/v1/suggestions");
      return SuggestionsResponseSchema.parse(raw).items;
    },
  });
}

/** El estado opuesto: el check togglea pending↔done. */
function flip(status: TaskStatus): TaskStatus {
  return status === "done" ? "pending" : "done";
}

/**
 * Togglea el estado de una prioridad (`PATCH /v1/tasks/{id}`) con **update
 * optimista**: el check responde al toque al instante y, si el request falla,
 * se revierte. `onSettled` re-sincroniza con el server por las dudas.
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
export type { Suggestion, Task, TasksResponse };
