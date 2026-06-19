"use client";

import { type CSSProperties, useEffect, useState } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { AUDIT_PAGE_SIZE, useAudit } from "@/features/audit/hooks/useAudit";
import { type AuditFilterState, EMPTY_AUDIT_FILTERS } from "@/features/audit/schemas";
import { cn } from "@/lib/cn";
import { useRangeStore } from "@/stores/range";
import { AuditFilters } from "./AuditFilters";
import { AuditTable } from "./AuditTable";

/**
 * Skeleton de la tabla mientras se trae la primera página (sin datos previos en
 * cache). Hairlines + shimmer, alineado con el `loading.tsx` del panel. Una vez
 * que hay datos, `keepPreviousData` evita volver a este estado (la tabla se
 * atenúa en su lugar).
 */
/** Claves estables para las filas del skeleton (cantidad fija, nunca reordena). */
const SKELETON_ROWS = ["s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7"] as const;

function TableSkeleton() {
  return (
    <div
      role="status"
      aria-label="Cargando eventos"
      className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)]"
    >
      <div className="border-b border-[var(--color-border-strong)] px-4 py-3">
        <div className="anim-pulse-soft h-3 w-40 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]" />
      </div>
      {SKELETON_ROWS.map((rowKey) => (
        <div key={rowKey} className="border-b border-[var(--color-border)] px-4 py-3">
          <div className="anim-pulse-soft h-4 w-full rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)]" />
        </div>
      ))}
    </div>
  );
}

/**
 * Composición interactiva de la pantalla F1.5 — Audit Log soberano (blueprint
 * §3). Vive en un client component porque es dueña del estado de filtros + página
 * y consume el rango global del store; el `page.tsx` server-side aporta el header
 * editorial y la metadata.
 *
 * Flujo: `AuditFilters` (sticky) muta el estado de filtros → cualquier cambio de
 * filtro o de rango resetea la paginación a la página 0 (no tendría sentido
 * mantener la página 5 de un conjunto que cambió). `useAudit` re-parsea el
 * payload con el Zod (frontera de privacidad: `record_hash`/`target_id` no
 * existen en el tipo). `AuditTable` pinta filas + banner soberano + paginación.
 *
 * Estados cuidados: primera carga → skeleton; error → `EmptyStateCard` con el
 * mensaje; fetching de página/filtro nuevo → la tabla se atenúa sobre la data
 * previa (vía `keepPreviousData`).
 */
export function AuditScreen() {
  const range = useRangeStore((s) => s.range);
  const [filters, setFilters] = useState<AuditFilterState>(EMPTY_AUDIT_FILTERS);
  const [page, setPage] = useState(0);

  // Cambiar el rango global invalida la paginación: volver a la primera página.
  // biome-ignore lint/correctness/useExhaustiveDependencies: `range` es el disparador intencional del reset (no se usa en el cuerpo, pero su cambio es lo que debe re-correr el efecto); quitarlo rompería el reset-on-range-change.
  useEffect(() => {
    setPage(0);
  }, [range]);

  const handleFilters = (next: AuditFilterState) => {
    setFilters(next);
    setPage(0);
  };

  const query = useAudit(range, filters, page);

  return (
    <div className="flex flex-col gap-8">
      {/* Banda 1 — filtros sticky (col-span-12). */}
      <div className="anim-stagger-up" style={{ "--stagger-index": 0 } as CSSProperties}>
        <AuditFilters value={filters} onChange={handleFilters} />
      </div>

      {/* Banda 2 — tabla + banner soberano (col-span-12). */}
      <div className="anim-stagger-up" style={{ "--stagger-index": 1 } as CSSProperties}>
        {query.isLoading ? (
          <TableSkeleton />
        ) : query.isError ? (
          <EmptyStateCard
            title="No se pudo cargar el audit log"
            hint={
              query.error?.status
                ? `Error ${query.error.status}. Reintentá o ajustá los filtros.`
                : "Reintentá en unos segundos o ajustá los filtros."
            }
          />
        ) : query.data ? (
          <AuditTable
            rows={query.data.items}
            total={query.data.total}
            sensitive_pct={query.data.sensitive_pct}
            page={page}
            pageSize={AUDIT_PAGE_SIZE}
            onPage={setPage}
            isFetching={query.isFetching && query.isPlaceholderData}
            className={cn(query.isPlaceholderData && "pointer-events-none")}
          />
        ) : null}
      </div>
    </div>
  );
}
