"use client";

import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useTasks, useToggleTask } from "../api";
import { HoyEmptyState } from "./HoyEmptyState";
import { PrioritiesSkeleton } from "./PrioritiesSkeleton";
import { PriorityRow } from "./PriorityRow";

/**
 * Sección **Prioridades del día** (wireframe 06 / build-plan E2). Conecta a
 * `GET /v1/tasks` (mock) vía `useTasks` y resuelve los 4 estados: cargando
 * (skeleton), error (con reintento), vacío y la lista con el check optimista
 * (`useToggleTask`).
 *
 * Día despejado (sin prioridades) → composición completa de "Hoy vacío"
 * (`HoyEmptyState`, wireframe 07 / build-plan E5), sin el encabezado
 * "Prioridades" (no hay prioridades que titular).
 */
export function PrioritiesSection() {
  const { data, isPending, isError, refetch, isFetching } = useTasks();
  const toggle = useToggleTask();

  if (!isPending && !isError && data.length === 0) {
    return <HoyEmptyState />;
  }

  return (
    <section className="flex flex-col gap-3" aria-busy={isPending}>
      <h2 className="text-caption text-[var(--color-ink-soft)]">Prioridades del día</h2>

      {isPending ? (
        <PrioritiesSkeleton />
      ) : isError ? (
        <EmptyStateCard
          title="No pudimos traer tus prioridades"
          hint="Puede ser un problema de conexión. Probá de nuevo."
          action={
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="text-button text-[var(--color-ink)] underline underline-offset-4 disabled:opacity-50"
            >
              Reintentar
            </button>
          }
        />
      ) : (
        <ul className="flex flex-col divide-y divide-[var(--color-border)]">
          {data.map((task, index) => (
            <PriorityRow key={task.id} task={task} index={index} onToggle={toggle.mutate} />
          ))}
        </ul>
      )}
    </section>
  );
}
