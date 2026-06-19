"use client";

import { type CSSProperties, useId, useMemo, useState } from "react";
import type { HeatLevel } from "@/features/_shared/schemas";
import { cn } from "@/lib/cn";
import { fmtInt } from "@/lib/time";
import { heatmapLayout } from "./chart-utils";

type Cell = { date: string; count: number; level: HeatLevel };

type Props = {
  /** Celdas en orden cronológico ascendente (idealmente ~53 semanas × 7 días). */
  cells: Cell[];
  /**
   * Rótulo de honestidad de dato (blueprint §0, regla #6). P.ej. "actividad
   * estimada por sesiones". Se muestra como caption bajo el grid.
   */
  note?: string;
  className?: string;
};

/** Token de fondo por nivel de intensidad (escala plana de azul, §0.1). */
const HEAT_VAR: Record<HeatLevel, string> = {
  0: "var(--heat-0)",
  1: "var(--heat-1)",
  2: "var(--heat-2)",
  3: "var(--heat-3)",
  4: "var(--heat-4)",
  5: "var(--heat-5)",
};

const LEGEND_LEVELS: HeatLevel[] = [0, 1, 2, 3, 4, 5];

/**
 * Heatmap estilo "contribuciones" (columnas = semanas, filas = días). Intensidad
 * por nivel discreto usando la escala plana de azul `--heat-1..5` sobre
 * `--heat-0` (sin gradiente). Tooltip con fecha + count `tabular-nums`, leyenda
 * "menos → más", y un stagger por columna en el primer load (barrido izq→der).
 * `note` rotula el proxy de dato cuando el conteo no es una medida directa.
 */
export function UsageHeatmap({ cells, note, className }: Props) {
  const labelId = useId();
  const [hover, setHover] = useState<Cell | null>(null);
  const laid = useMemo(() => heatmapLayout(cells), [cells]);

  if (cells.length === 0) {
    return (
      <p className={cn("text-body-sm text-[var(--color-ink-soft)]", className)}>
        Sin datos en el rango.
      </p>
    );
  }

  return (
    <figure className={cn("flex flex-col gap-3", className)} aria-labelledby={labelId}>
      <figcaption id={labelId} className="sr-only">
        Actividad diaria por semana.{note ? ` ${note}.` : ""}
      </figcaption>

      <div className="relative">
        <div
          className="grid grid-flow-col scrollbar-none overflow-x-auto"
          style={{ gridTemplateRows: "repeat(7, 1fr)", gap: 3 }}
          role="img"
          aria-label={`Mapa de calor de actividad${note ? `. ${note}` : ""}`}
        >
          {laid.map((cell) => (
            <button
              type="button"
              key={cell.date}
              className="anim-stagger-up h-[11px] w-[11px] rounded-[3px] outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
              style={
                {
                  gridColumn: cell.col + 1,
                  gridRow: cell.row + 1,
                  backgroundColor: HEAT_VAR[cell.level],
                  // Stagger por columna → barrido izq→der; capado a ~6 índices.
                  "--stagger-index": Math.min(cell.col, 6),
                } as CSSProperties
              }
              onMouseEnter={() => setHover(cell)}
              onMouseLeave={() => setHover((cur) => (cur === cell ? null : cur))}
              onFocus={() => setHover(cell)}
              onBlur={() => setHover((cur) => (cur === cell ? null : cur))}
              aria-label={`${cell.date}: ${fmtInt(cell.count)}`}
            />
          ))}
        </div>

        {hover ? (
          <div
            role="status"
            className="anim-fade-in pointer-events-none absolute -top-1 left-0 z-[var(--z-sticky)] -translate-y-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-glass)] px-2.5 py-1.5 shadow-soft"
          >
            <p className="text-caption text-[var(--color-ink-soft)]">{hover.date}</p>
            <p className="text-body-sm tabular-nums text-[var(--color-ink-deep)]">
              {fmtInt(hover.count)}
            </p>
          </div>
        ) : null}
      </div>

      {/* Leyenda menos → más + rótulo de proxy. */}
      <div className="flex items-center justify-between gap-4">
        {note ? (
          <p className="text-caption text-[var(--color-ink-soft)]">{note}</p>
        ) : (
          <span aria-hidden />
        )}
        <div className="flex items-center gap-1.5">
          <span className="text-caption text-[var(--color-ink-soft)]">Menos</span>
          {LEGEND_LEVELS.map((lvl) => (
            <span
              key={lvl}
              aria-hidden
              className="h-[11px] w-[11px] rounded-[3px]"
              style={{ backgroundColor: HEAT_VAR[lvl] }}
            />
          ))}
          <span className="text-caption text-[var(--color-ink-soft)]">Más</span>
        </div>
      </div>
    </figure>
  );
}
