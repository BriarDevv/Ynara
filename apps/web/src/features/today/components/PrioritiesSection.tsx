"use client";

import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useTasks, useToggleTask } from "../api";
import { PrioritiesSkeleton } from "./PrioritiesSkeleton";
import { PriorityRow } from "./PriorityRow";

/**
 * Sección **Prioridades del día** (wireframe 06 / build-plan E2). Conecta a
 * `GET /v1/tasks` (mock) vía `useTasks` y resuelve los 4 estados: cargando
 * (skeleton), error (con reintento), vacío (hint compacto) y la lista con el
 * check optimista (`useToggleTask`).
 *
 * El vacío de tareas acá es compacto a propósito: la composición completa del
 * "Hoy vacío" (wireframe 07: card grande + próximo bloque) es la Fase E4.
 */
export function PrioritiesSection() {
  const { data, isPending, isError, refetch, isFetching } = useTasks();
  const toggle = useToggleTask();

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-caption text-[var(--color-ink-muted)]">Prioridades del día</h2>

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
      ) : data.length === 0 ? (
        <EmptyStateCard
          field
          title="Sin urgentes esta hora"
          hint="Aprovechá el tiempo libre, o pedile algo a Ynara."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {data.map((task, index) => (
            <PriorityRow key={task.id} task={task} index={index} onToggle={toggle.mutate} />
          ))}
        </ul>
      )}
    </section>
  );
}
