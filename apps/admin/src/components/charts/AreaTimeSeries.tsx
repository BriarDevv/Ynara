"use client";

import { useId, useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { fmtInt } from "@/lib/time";
import {
  areaPath,
  type ChartBox,
  extent,
  linePath,
  niceTicks,
  plotWidth,
  projectSeries,
  type SeriesPoint,
  scaleLinear,
} from "./chart-utils";

type Props = {
  /** Serie temporal única (p.ej. sesiones/día), orden cronológico ascendente. */
  points: SeriesPoint[];
  /** Alto del `viewBox` en px. El ancho es fluido. */
  height?: number;
  /** Etiqueta del eje/serie y del tooltip (p.ej. "Sesiones"). */
  valueLabel: string;
  className?: string;
};

const VIEW_WIDTH = 720;

/**
 * Serie temporal de un solo valor: línea azul plana + área de relleno a
 * `opacity 0.12` **plana** (sin gradiente, respeta el gradient-guard). Ejes con
 * `tabular-nums`, grid horizontal por `--color-border`, y tooltip por punto al
 * pasar el mouse. Pensada para sesiones/día del Overview.
 */
export function AreaTimeSeries({ points, height = 240, valueLabel, className }: Props) {
  const labelId = useId();
  const [hover, setHover] = useState<number | null>(null);

  const box: ChartBox = useMemo(
    () => ({ width: VIEW_WIDTH, height, padding: { top: 12, right: 12, bottom: 28, left: 44 } }),
    [height],
  );

  const { coords, ticks, baselineY, line, area, xFor } = useMemo(() => {
    const values = points.map((p) => p.value);
    const { max } = extent(values);
    const yMax = max === 0 ? 1 : max;
    const projected = projectSeries(points, box, { yMin: 0, yMax });
    const yScale = scaleLinear(0, yMax, box.padding.top + plotHeightOf(box), box.padding.top);
    const tickVals = niceTicks(0, yMax, 4);
    const base = box.padding.top + plotHeightOf(box);
    const xScale = scaleLinear(
      0,
      Math.max(1, points.length - 1),
      box.padding.left,
      box.padding.left + plotWidth(box),
    );
    return {
      coords: projected,
      ticks: tickVals.map((v) => ({ value: v, y: yScale(v) })),
      baselineY: base,
      line: linePath(projected),
      area: areaPath(projected, base),
      xFor: (i: number) => xScale(i),
    };
  }, [points, box]);

  if (points.length === 0) {
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

  const hovered = hover != null ? points[hover] : null;

  return (
    <figure className={cn("relative w-full", className)} aria-labelledby={labelId}>
      <figcaption id={labelId} className="sr-only">
        {valueLabel} por día en el rango.
      </figcaption>
      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={`${valueLabel} por día`}
      >
        {/* Grid horizontal + labels del eje Y (tabular-nums). */}
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

        {/* Área plana (opacity 0.12) + línea azul. */}
        <path d={area} fill="var(--color-azul)" fillOpacity={0.12} stroke="none" />
        <path
          d={line}
          fill="none"
          stroke="var(--color-azul)"
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />

        {/* Punto resaltado + guía vertical en hover. */}
        {hover != null && coords[hover] ? (
          <g>
            <line
              x1={coords[hover].x}
              x2={coords[hover].x}
              y1={box.padding.top}
              y2={baselineY}
              stroke="var(--color-border-strong)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
            <circle
              cx={coords[hover].x}
              cy={coords[hover].y}
              r={3.5}
              fill="var(--color-azul)"
              stroke="var(--color-bg)"
              strokeWidth={1.5}
            />
          </g>
        ) : null}

        {/* Bandas invisibles de hit-test por punto (tooltip). */}
        {points.map((p, i) => {
          const w = plotWidth(box) / Math.max(1, points.length);
          return (
            // biome-ignore lint/a11y/noStaticElementInteractions: enhancement de hover solo-mouse sobre un chart que ya es accesible vía el `role="img"` + aria-label del <svg>; las bandas no aportan contenido semántico (darles un role las anunciaría como interactivas sin serlo).
            <rect
              key={p.date}
              x={xFor(i) - w / 2}
              y={box.padding.top}
              width={w}
              height={baselineY - box.padding.top}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((cur) => (cur === i ? null : cur))}
            />
          );
        })}
      </svg>

      {hovered ? (
        <div
          className="anim-fade-in pointer-events-none absolute top-0 z-[var(--z-sticky)] -translate-x-1/2 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-glass)] px-2.5 py-1.5 shadow-soft"
          style={{ left: `${((hover ?? 0) / Math.max(1, points.length - 1)) * 100}%` }}
        >
          <p className="text-caption text-[var(--color-ink-soft)]">{hovered.date}</p>
          <p className="text-body-sm tabular-nums text-[var(--color-ink-deep)]">
            {fmtInt(hovered.value)} {valueLabel.toLowerCase()}
          </p>
        </div>
      ) : null}
    </figure>
  );
}

/** Alto útil del plot (helper local: evita re-importar para una sola cuenta). */
function plotHeightOf(box: ChartBox): number {
  return box.height - box.padding.top - box.padding.bottom;
}
