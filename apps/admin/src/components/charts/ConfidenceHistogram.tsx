"use client";

import { useId, useMemo } from "react";
import { cn } from "@/lib/cn";
import { fmtInt, fmtPct } from "@/lib/time";
import { extent } from "./chart-utils";

type Bucket = { range: string; count: number };

type Props = {
  /** Buckets de `confidence` (0–1), p.ej. `[{ range: "0.0–0.2", count: 4 }, …]`. */
  buckets: Bucket[];
  /** Memorias procedurales marcadas `stale` (se pinta en `--color-error`). */
  staleCount: number;
  /** Memorias procedurales sanas (para el % de salud). */
  healthyCount: number;
  className?: string;
};

/**
 * Distribución de `confidence` de las memorias procedurales: barras verticales
 * planas azules por bucket + una barra de `stale` en `--color-error` (la única
 * señal "roja" del chart: lo que perdió vigencia). Eje de conteo y % de stale
 * con `tabular-nums`. Sin ejes recargados, sin gradiente.
 */
export function ConfidenceHistogram({ buckets, staleCount, healthyCount, className }: Props) {
  const labelId = useId();

  const { bars, maxCount } = useMemo(() => {
    // La barra de stale entra al mismo eje que los buckets para comparar alturas.
    const all = [...buckets.map((b) => b.count), staleCount];
    const { max } = extent(all);
    return { bars: buckets, maxCount: max === 0 ? 1 : max };
  }, [buckets, staleCount]);

  const stalePct = useMemo(() => {
    const denom = staleCount + healthyCount;
    return denom === 0 ? 0 : (staleCount / denom) * 100;
  }, [staleCount, healthyCount]);

  if (buckets.length === 0) {
    return (
      <p className={cn("text-body-sm text-[var(--color-ink-soft)]", className)}>
        Sin datos en el rango.
      </p>
    );
  }

  return (
    <figure className={cn("flex flex-col gap-3", className)} aria-labelledby={labelId}>
      <figcaption id={labelId} className="sr-only">
        Distribución de confianza de memorias procedurales. {fmtPct(stalePct)} stale.
      </figcaption>

      <div className="flex h-40 items-end gap-2" role="img" aria-label="Histograma de confianza">
        {bars.map((b) => (
          <div
            key={b.range}
            className="flex h-full flex-1 flex-col items-center justify-end gap-1.5"
          >
            <span className="text-caption tabular-nums text-[var(--color-ink-soft)]">
              {fmtInt(b.count)}
            </span>
            <div
              className="anim-stagger-up w-full origin-bottom rounded-t-[var(--radius-sm)] bg-[var(--color-azul)]"
              style={{ height: `${(b.count / maxCount) * 100}%` }}
            />
            <span className="text-caption text-[var(--color-ink-soft)]">{b.range}</span>
          </div>
        ))}

        {/* Separador + barra de stale (error). */}
        <div aria-hidden className="h-full w-px self-stretch bg-[var(--color-border)]" />
        <div className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
          <span className="text-caption tabular-nums text-[var(--color-ink-soft)]">
            {fmtInt(staleCount)}
          </span>
          <div
            className="anim-stagger-up w-full origin-bottom rounded-t-[var(--radius-sm)] bg-[var(--color-error)]"
            style={{ height: `${(staleCount / maxCount) * 100}%` }}
          />
          <span className="text-caption text-[var(--color-ink-soft)]">stale</span>
        </div>
      </div>

      <p className="text-body-sm text-[var(--color-ink-soft)]">
        <span className="tabular-nums text-[var(--color-error)]">{fmtPct(stalePct)}</span> de las
        memorias procedurales perdió vigencia.
      </p>
    </figure>
  );
}
