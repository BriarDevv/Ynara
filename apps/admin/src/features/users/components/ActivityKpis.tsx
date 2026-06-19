"use client";

import { type CSSProperties, useId, useState } from "react";
import { Sparkline } from "@/components/charts/Sparkline";
import { Card } from "@/components/ui/Card";
import type { AdminUsersOutT } from "@/features/users/schemas";
import { useCountUp } from "@/hooks/useCountUp";
import { cn } from "@/lib/cn";
import { fmtDelta, fmtInt } from "@/lib/time";

/** Una de las tres ventanas de actividad. */
type ActivityMetric = AdminUsersOutT["activity"]["dau"];

type TileProps = {
  /** Sigla de la métrica (DAU/WAU/MAU). */
  label: string;
  /** Nombre largo, para el aria-label y el tooltip. */
  longLabel: string;
  metric: ActivityMetric;
  /** Índice para el stagger anidado de entrada (§5). */
  staggerIndex: number;
};

/** Mapa de la dirección del delta a su color de token (azul ▲ / error ▼ / neutro). */
const DELTA_COLOR: Record<ActivityMetric["delta"]["direction"], string> = {
  up: "var(--color-azul)",
  down: "var(--color-error)",
  flat: "var(--color-ink-soft)",
};

/** Glifo direccional del delta (triángulo ▲ / ▼ / cuadrado neutro). */
const DELTA_GLYPH: Record<ActivityMetric["delta"]["direction"], string> = {
  up: "▲",
  down: "▼",
  flat: "◆",
};

/**
 * Tile de actividad: eyebrow (sigla) → valor `text-hero` con count-up y
 * `tabular-nums` → pill de delta (glifo direccional ▲/▼/◆ + color por token) →
 * `<Sparkline/>`. Lleva un marcador "aprox." con tooltip que explica el proxy
 * (no hay `last_seen`; se deriva de sesiones). Entra con `anim-stagger-up`.
 */
function ActivityTile({ label, longLabel, metric, staggerIndex }: TileProps) {
  const tipId = useId();
  const [showTip, setShowTip] = useState(false);
  const animated = useCountUp(metric.value);
  const deltaColor = DELTA_COLOR[metric.delta.direction];

  return (
    <Card
      className="anim-stagger-up relative flex flex-col gap-4"
      style={{ "--stagger-index": Math.min(staggerIndex, 6) } as CSSProperties}
    >
      <header className="flex items-center justify-between gap-2">
        <p className="text-caption text-[var(--color-ink-soft)]">{label}</p>
        {/* Marcador de honestidad de dato (regla #6): proxy por sesiones. */}
        <button
          type="button"
          aria-describedby={tipId}
          aria-label={`${longLabel}: medida aproximada por sesiones`}
          className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-2 py-0.5 text-caption text-[var(--color-ink-soft)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
          onMouseEnter={() => setShowTip(true)}
          onMouseLeave={() => setShowTip(false)}
          onFocus={() => setShowTip(true)}
          onBlur={() => setShowTip(false)}
        >
          aprox.
        </button>
        {showTip ? (
          <div
            id={tipId}
            role="tooltip"
            className="anim-fade-in absolute right-4 top-12 z-[var(--z-sticky)] w-56 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-glass)] px-3 py-2 shadow-soft"
          >
            <p className="text-body-sm text-[var(--color-ink-soft)]">
              Aproximado por sesiones — no existe <code>last_seen</code>, así que la actividad se
              deriva de las sesiones del período.
            </p>
          </div>
        ) : null}
      </header>

      <p
        role="img"
        className="text-hero tabular-nums text-[var(--color-ink-deep)]"
        aria-label={`${fmtInt(metric.value)} ${longLabel}`}
      >
        {fmtInt(Math.round(animated))}
      </p>

      <div className="flex items-center gap-2">
        <span
          className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-2 py-0.5 text-caption tabular-nums"
          style={{ backgroundColor: "var(--color-bg-soft)", color: deltaColor }}
        >
          <span aria-hidden className="text-[0.625rem] leading-none">
            {DELTA_GLYPH[metric.delta.direction]}
          </span>
          {fmtDelta(metric.delta.pct)}
        </span>
        <span className="text-caption text-[var(--color-ink-soft)]">vs. período anterior</span>
      </div>

      <Sparkline data={metric.spark} aria-label={`Tendencia de ${longLabel}`} />
    </Card>
  );
}

type Props = {
  activity: AdminUsersOutT["activity"];
  className?: string;
};

/**
 * F1.2 · Banda 1 — Actividad (DAU / WAU / MAU).
 *
 * Tres tiles en cascada de stagger anidado. Cada métrica es un **proxy por
 * sesiones** (no hay `last_seen`): el schema lo clava con `isApproximate: true`
 * y cada tile lo rotula con un marcador "aprox." + tooltip (regla #6 de
 * honestidad de dato). Client component por el count-up, el tooltip y el hover.
 */
export function ActivityKpis({ activity, className }: Props) {
  const tiles: { label: string; longLabel: string; metric: ActivityMetric }[] = [
    { label: "DAU", longLabel: "usuarios activos por día", metric: activity.dau },
    { label: "WAU", longLabel: "usuarios activos por semana", metric: activity.wau },
    { label: "MAU", longLabel: "usuarios activos por mes", metric: activity.mau },
  ];

  return (
    <div className={cn("grid grid-cols-1 gap-6 sm:grid-cols-3", className)}>
      {tiles.map((t, i) => (
        <ActivityTile
          key={t.label}
          label={t.label}
          longLabel={t.longLabel}
          metric={t.metric}
          staggerIndex={i}
        />
      ))}
    </div>
  );
}
