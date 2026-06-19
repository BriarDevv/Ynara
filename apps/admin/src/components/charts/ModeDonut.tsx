"use client";

import { useId, useMemo } from "react";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { useCountUp } from "@/hooks/useCountUp";
import { cn } from "@/lib/cn";
import { fmtInt, fmtPct } from "@/lib/time";
import { donutSlicePath, sliceAngles } from "./chart-utils";

type Datum = { mode: ModeId; value: number };

type Props = {
  /** Una entrada por modo. Los slices se dibujan en el orden recibido. */
  data: Datum[];
  /** Total mostrado en el centro (se cuenta 0 → total al montar). */
  total: number;
  className?: string;
};

const SIZE = 200;
const CENTER = SIZE / 2;
const OUTER_R = 92;
const INNER_R = 60;

/**
 * Donut del mix de modos: cada slice con el `fillVar` oficial del modo (color
 * **plano**, sin gradiente). En el centro, el total en `text-display`
 * `tabular-nums` que cuenta 0 → total al primer load. Leyenda lateral con
 * `ModeChip` + conteo + porcentaje (`tabular-nums`).
 */
export function ModeDonut({ data, total, className }: Props) {
  const labelId = useId();
  const animated = useCountUp(total);
  const slices = useMemo(() => sliceAngles(data), [data]);

  if (data.length === 0 || total === 0) {
    return (
      <p className={cn("text-body-sm text-[var(--color-ink-soft)]", className)}>
        Sin datos en el rango.
      </p>
    );
  }

  return (
    <figure
      className={cn("flex flex-col items-center gap-6 sm:flex-row sm:items-center", className)}
      aria-labelledby={labelId}
    >
      <figcaption id={labelId} className="sr-only">
        Mix de sesiones por modo. Total {fmtInt(total)}.
      </figcaption>

      <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="h-full w-full"
          role="img"
          aria-label="Distribución de sesiones por modo"
        >
          {slices.map((s) => (
            <path
              key={s.mode}
              d={donutSlicePath({
                cx: CENTER,
                cy: CENTER,
                innerR: INNER_R,
                outerR: OUTER_R,
                startAngle: s.startAngle,
                endAngle: s.endAngle,
              })}
              fill={MODE_BY_ID[s.mode].fillVar}
              stroke="var(--color-bg)"
              strokeWidth={2}
            />
          ))}
        </svg>
        {/* Total centrado: number-grande con count-up. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-display tabular-nums leading-none text-[var(--color-ink-deep)]">
            {fmtInt(Math.round(animated))}
          </span>
          <span className="text-caption text-[var(--color-ink-soft)]">sesiones</span>
        </div>
      </div>

      <ul className="flex w-full flex-col gap-2">
        {slices.map((s) => (
          <li key={s.mode} className="flex items-center justify-between gap-3">
            <ModeChip modeId={s.mode} label={MODE_BY_ID[s.mode].label} size="sm" />
            <span className="text-body-sm tabular-nums text-[var(--color-ink-soft)]">
              {fmtInt(s.value)}
              <span className="ml-2 text-[var(--color-ink-muted)]">{fmtPct(s.fraction * 100)}</span>
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
