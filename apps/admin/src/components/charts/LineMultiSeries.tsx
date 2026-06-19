"use client";

import { useId, useMemo } from "react";
import { cn } from "@/lib/cn";
import { fmtInt } from "@/lib/time";
import {
  type ChartBox,
  extent,
  linePath,
  niceTicks,
  projectSeries,
  type SeriesPoint,
  scaleLinear,
} from "./chart-utils";

/** Capa del moat: clave canónica + color por token + etiqueta de leyenda. */
type LayerKey = "semantic" | "episodic" | "procedural";

type LayerSeries = { key: LayerKey; points: SeriesPoint[] };

type Props = {
  /** Hasta 3 series, una por capa de memoria. */
  series: LayerSeries[];
  /** Alto del `viewBox`. El ancho es fluido. */
  height?: number;
  className?: string;
};

const VIEW_WIDTH = 720;

/**
 * Color y etiqueta de cada capa. El color sale de los alias semánticos
 * `--layer-*` (que apuntan a los tints oficiales) — color **plano**, sin
 * relleno ni gradiente. La leyenda documenta el código de color para que el
 * lector sepa qué línea es cuál.
 */
const LAYER_META: Record<LayerKey, { label: string; colorVar: string }> = {
  semantic: { label: "Semántica", colorVar: "var(--layer-semantic)" },
  episodic: { label: "Episódica", colorVar: "var(--layer-episodic)" },
  procedural: { label: "Procedural", colorVar: "var(--layer-procedural)" },
};

/**
 * Tres líneas planas (una por capa de memoria) sobre ejes compartidos, para el
 * crecimiento del moat. Sin relleno; cada línea con su color de capa por token.
 * Leyenda lateral que mapea color → capa. Ejes con `tabular-nums`.
 */
export function LineMultiSeries({ series, height = 240, className }: Props) {
  const labelId = useId();

  const box: ChartBox = useMemo(
    () => ({ width: VIEW_WIDTH, height, padding: { top: 12, right: 12, bottom: 28, left: 48 } }),
    [height],
  );

  const { lines, ticks } = useMemo(() => {
    const allValues = series.flatMap((s) => s.points.map((p) => p.value));
    const { max } = extent(allValues);
    const yMax = max === 0 ? 1 : max;
    const plotH = box.height - box.padding.top - box.padding.bottom;
    const yScale = scaleLinear(0, yMax, box.padding.top + plotH, box.padding.top);
    return {
      lines: series.map((s) => ({
        key: s.key,
        d: linePath(projectSeries(s.points, box, { yMin: 0, yMax })),
      })),
      ticks: niceTicks(0, yMax, 4).map((v) => ({ value: v, y: yScale(v) })),
    };
  }, [series, box]);

  const empty = series.every((s) => s.points.length === 0);
  if (empty) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-[var(--radius-md)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)] text-body-sm text-[var(--color-ink-soft)]",
          className,
        )}
        style={{ height }}
      >
        Sin datos en el rango.
      </div>
    );
  }

  return (
    <figure className={cn("flex w-full flex-col gap-3", className)} aria-labelledby={labelId}>
      <figcaption id={labelId} className="sr-only">
        Crecimiento de las tres capas de memoria en el rango.
      </figcaption>
      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label="Crecimiento por capa de memoria"
      >
        {ticks.map((t) => (
          <g key={t.value}>
            <line
              x1={box.padding.left}
              x2={VIEW_WIDTH - box.padding.right}
              y1={t.y}
              y2={t.y}
              stroke="var(--color-border)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
            <text
              x={box.padding.left - 8}
              y={t.y}
              textAnchor="end"
              dominantBaseline="middle"
              className="fill-[var(--color-ink-soft)] text-[10px] tabular-nums"
            >
              {fmtInt(t.value)}
            </text>
          </g>
        ))}
        {lines.map((l) => (
          <path
            key={l.key}
            d={l.d}
            fill="none"
            stroke={LAYER_META[l.key].colorVar}
            strokeWidth={1.5}
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>

      {/* Leyenda: documenta el código de color de capa. */}
      <ul className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <span
              aria-hidden
              className="h-0.5 w-4 shrink-0 rounded-[var(--radius-pill)]"
              style={{ backgroundColor: LAYER_META[s.key].colorVar }}
            />
            <span className="text-body-sm text-[var(--color-ink-soft)]">
              {LAYER_META[s.key].label}
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
