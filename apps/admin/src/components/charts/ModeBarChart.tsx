"use client";

import { type CSSProperties, useMemo } from "react";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import { fmtValue } from "@/lib/time";
import { extent } from "./chart-utils";

type Datum = { mode: ModeId; value: number; label: string };

type Props = {
  /** Una entrada por modo; se ordena desc por valor internamente. */
  data: Datum[];
  /** Formato del valor mostrado a la derecha de cada barra. Default `int`. */
  valueFormat?: "int" | "pct" | "min";
  className?: string;
};

/**
 * Barras horizontales por modo, relleno **plano** con el `fillVar` oficial del
 * modo (texto blanco AA encima si hiciera falta; acá el valor va al costado).
 * Cada fila: `ModeChip` (label + dot teñido) + barra proporcional + valor
 * `tabular-nums`. Orden descendente. Las barras crecen con `scaleX` desde 0 al
 * montar (se neutraliza bajo `html.motion-off`). Sin ejes, sin gradiente.
 */
export function ModeBarChart({ data, valueFormat = "int", className }: Props) {
  const sorted = useMemo(() => [...data].sort((a, b) => b.value - a.value), [data]);
  const { max } = useMemo(() => extent(sorted.map((d) => d.value)), [sorted]);
  const denom = max === 0 ? 1 : max;

  if (sorted.length === 0) {
    return (
      <p className={cn("text-body-sm text-[var(--color-ink-soft)]", className)}>
        Sin datos en el rango.
      </p>
    );
  }

  return (
    <ul className={cn("flex flex-col gap-3", className)} aria-label="Distribución por modo">
      {sorted.map((d, i) => {
        const mode = MODE_BY_ID[d.mode];
        const pct = (d.value / denom) * 100;
        return (
          <li key={d.mode} className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-3">
              <ModeChip modeId={d.mode} label={d.label} size="sm" />
              <span className="text-body-sm tabular-nums text-[var(--color-ink-deep)]">
                {fmtValue(d.value, valueFormat)}
              </span>
            </div>
            {/* Riel de la barra: track suave + relleno plano del modo. */}
            <div
              className="h-2 w-full overflow-hidden rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]"
              role="presentation"
            >
              <div
                className="anim-stagger-up h-full origin-left rounded-[var(--radius-pill)]"
                style={
                  {
                    width: `${pct}%`,
                    backgroundColor: mode.fillVar,
                    // Crecimiento escalonado por fila; bajo motion-off queda full.
                    "--stagger-index": Math.min(i, 6),
                  } as CSSProperties
                }
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
