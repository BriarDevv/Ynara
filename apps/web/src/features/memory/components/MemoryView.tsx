"use client";

import { useMemo, useState } from "react";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { type TimelineFilter, useMemoryTimeline } from "../api";
import { groupByBucket } from "../timeline";
import { MemorySearchLink } from "./MemorySearchLink";
import { MemoryTimelineSkeleton } from "./MemoryTimelineSkeleton";
import { TimelineEntryRow } from "./TimelineEntryRow";

const FILTER_OPTIONS: readonly { value: TimelineFilter; label: string }[] = [
  { value: "all", label: "Todo" },
  { value: "semantic", label: "Hechos" },
  { value: "episodic", label: "Momentos" },
  { value: "procedural", label: "Costumbres" },
];

/**
 * Vista **Memoria** (timeline, wireframe 17 / build-plan C1). Conecta a
 * `GET /v1/memory` vía `useMemoryTimeline` y resuelve los 4 estados: cargando
 * (skeleton), error (con reintento), vacío (estado editorial) y la lista
 * cronológica agrupada por bucket temporal.
 *
 * Sube fidelidad sobre el wireframe con el design system v2: header editorial,
 * filtros por capa con etiquetas cálidas, badges del set de íconos propio.
 */
export function MemoryView() {
  const [filter, setFilter] = useState<TimelineFilter>("all");
  const { data, isPending, isError, refetch, isFetching } = useMemoryTimeline(filter);

  // `now` estable durante la vida de la vista: ancla los buckets y las fechas
  // relativas sin re-evaluar en cada render.
  const [now] = useState(() => new Date());
  const groups = useMemo(() => (data ? groupByBucket(data, now) : []), [data, now]);

  return (
    <div className="mx-auto flex w-full max-w-[680px] flex-col gap-6 px-6 pb-10 pt-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-title text-[var(--color-ink-deep)]">Memoria</h1>
        <p className="text-body text-[var(--color-ink-soft)]">
          Todo lo que Ynara fue guardando con vos, en orden.
        </p>
      </header>

      <MemorySearchLink />

      <ChipGroup
        label="Filtrar por tipo"
        options={FILTER_OPTIONS}
        value={filter}
        onChange={setFilter}
      />

      {isPending ? (
        <MemoryTimelineSkeleton />
      ) : isError ? (
        <EmptyStateCard
          title="No pudimos traer tu memoria"
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
      ) : groups.length === 0 ? (
        <EmptyStateCard
          title="Todavía no hay nada acá"
          hint="A medida que charlen, Ynara va a ir recordando lo importante. Esto se llena solo."
        />
      ) : (
        <div className="flex flex-col gap-8">
          {(() => {
            // Índice continuo entre grupos para que el stagger no se reinicie.
            let runningIndex = 0;
            return groups.map((group) => (
              <section key={group.bucket} className="flex flex-col gap-3">
                <h2 className="text-caption text-[var(--color-ink-soft)]">{group.bucket}</h2>
                <ul className="flex flex-col gap-3">
                  {group.entries.map((entry) => (
                    <TimelineEntryRow
                      key={`${entry.layer}:${entry.ref}`}
                      entry={entry}
                      now={now}
                      index={runningIndex++}
                    />
                  ))}
                </ul>
              </section>
            ));
          })()}
        </div>
      )}
    </div>
  );
}
