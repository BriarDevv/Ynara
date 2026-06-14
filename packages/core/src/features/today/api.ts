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
import { api } from "../../api";
import { qk } from "../../query-keys";

/**
 * Hooks de data de "Hoy", compartidos web + mobile (ADR-012). Validación Zod
 * en cliente: un contrato roto se ve en dev.
 *
 * PROVISIONAL: hoy corren contra mocks (no hay backend de tareas todavía —
 * `/v1/tasks`, `/v1/suggestions`, `/v1/recap`).
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

export function useSuggestions() {
  return useQuery({
    queryKey: qk.today.suggestions(),
    queryFn: async (): Promise<Suggestion[]> => {
      const raw = await api.get<unknown>("/v1/suggestions");
      return SuggestionsResponseSchema.parse(raw).items;
    },
  });
}

export function useRecap() {
  return useQuery({
    queryKey: qk.today.recap(),
    queryFn: async (): Promise<Recap> => {
      const raw = await api.get<unknown>("/v1/recap");
      return RecapSchema.parse(raw);
    },
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
