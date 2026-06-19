"use client";

import { Button } from "@/components/ui/Button";
import { Diamond } from "@/components/ui/Diamond";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import type { AdminAuditRowT } from "@/features/audit/schemas";
import { cn } from "@/lib/cn";
import { fmtInt, fmtPct } from "@/lib/time";
import { AuditRow } from "./AuditRow";

/**
 * Grilla compartida por el header y cada `AuditRow`: 6 columnas alineadas
 * (timestamp · operación · capa · modo · origen · sensible). Definida una sola
 * vez acá y duplicada en `AuditRow` para que header y filas no se desalineen si
 * se toca una. Última columna angosta (solo el Diamond de sensibilidad).
 */
const GRID_COLS = "grid-cols-[8rem_9rem_8.5rem_minmax(0,1fr)_minmax(0,1fr)_3rem]";

/** Columnas del header — `text-caption` uppercase (estilo tabla editorial). */
const HEADERS = ["Cuándo", "Operación", "Capa", "Modo", "Origen", "Sens."] as const;

type Props = {
  rows: AdminAuditRowT[];
  /** Total de la query CON filtros (no la tabla entera) — base de la paginación. */
  total: number;
  /** % de filas sensibles dentro del conjunto filtrado (honestidad de dato). */
  sensitive_pct: number;
  /** Página actual, 0-indexed. */
  page: number;
  pageSize: number;
  onPage: (page: number) => void;
  /** True mientras se trae una página/filtro nuevo (atenúa la tabla, no parpadea). */
  isFetching?: boolean;
  className?: string;
};

/**
 * Tabla soberana del audit log (blueprint §2.3 + §3 F1.5).
 *
 * Tabla editorial: hairlines entre filas (NO cajas, NO zebra), header sticky bajo
 * los filtros, orden `createdAt` desc (lo trae el backend/fixture), `tabular-nums`
 * en tiempos y en el contador de paginación. Paginación `limit/offset` con
 * botones prev/next.
 *
 * Banner soberano al pie: declara explícitamente que la vista NO expone el hash
 * de integridad ni el contenido descifrado — y eso es verdad estructural, no
 * cosmética: `AdminAuditRow` omite `record_hash`/`target_id` del schema (regla
 * #6). El % de sensibles se rotula como proxy del conjunto filtrado.
 *
 * Estados: vacío (sin resultados para los filtros) → `EmptyStateCard`; fetching
 * de una página nueva → opacidad reducida sobre la página previa (via
 * `keepPreviousData` en el hook).
 */
export function AuditTable({
  rows,
  total,
  sensitive_pct,
  page,
  pageSize,
  onPage,
  isFetching = false,
  className,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const from = total === 0 ? 0 : currentPage * pageSize + 1;
  const to = Math.min(total, (currentPage + 1) * pageSize);
  const hasPrev = currentPage > 0;
  const hasNext = currentPage + 1 < totalPages;

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)]">
        {/* Header sticky bajo los filtros (z bajo el sticky de AuditFilters). */}
        <div
          className={cn(
            "grid items-center gap-4 border-b border-[var(--color-border-strong)] bg-[var(--color-bg)] px-4 py-3",
            GRID_COLS,
          )}
        >
          {HEADERS.map((label, i) => (
            <span
              key={label}
              className={cn(
                "text-caption text-[var(--color-ink-soft)]",
                // La última columna (Sens.) centra para alinear con el Diamond.
                i === HEADERS.length - 1 && "text-center",
              )}
            >
              {label}
            </span>
          ))}
        </div>

        {/* Cuerpo */}
        {rows.length === 0 ? (
          <div className="p-6">
            <EmptyStateCard
              title="Sin eventos para estos filtros"
              hint="Ajustá la operación, la capa o el modo — o ampliá el rango temporal en el topbar."
            />
          </div>
        ) : (
          <div
            className={cn(
              "transition-opacity duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
              isFetching && "opacity-60",
            )}
            aria-busy={isFetching}
          >
            {rows.map((row, i) => (
              <AuditRow key={row.id} row={row} staggerIndex={Math.min(i, 6)} />
            ))}
          </div>
        )}
      </div>

      {/* Banner soberano + paginación */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-caption inline-flex items-center gap-2 text-[var(--color-ink-soft)]">
          <Diamond size={9} color="var(--color-azul)" />
          Vista soberana — sin hash de integridad ni contenido descifrado.
          {total > 0 ? (
            <span className="text-[var(--color-ink-muted)]">
              {" "}
              <span className="tabular-nums">{fmtPct(sensitive_pct)}</span> sensibles (aprox.)
            </span>
          ) : null}
        </p>

        <div className="flex items-center gap-3">
          <span className="text-body-sm tabular-nums text-[var(--color-ink-soft)]">
            {total === 0 ? (
              "0 eventos"
            ) : (
              <>
                {fmtInt(from)}–{fmtInt(to)} de {fmtInt(total)}
              </>
            )}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => onPage(currentPage - 1)}
              disabled={!hasPrev || isFetching}
              aria-label="Página anterior"
            >
              Anterior
            </Button>
            <Button
              variant="secondary"
              onClick={() => onPage(currentPage + 1)}
              disabled={!hasNext || isFetching}
              aria-label="Página siguiente"
            >
              Siguiente
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
