"use client";

import { type CSSProperties, useId, useState } from "react";
import { Card } from "@/components/ui/Card";
import type { AdminUsersOutT } from "@/features/users/schemas";
import { useCountUp } from "@/hooks/useCountUp";
import { cn } from "@/lib/cn";
import { fmtInt, fmtPct } from "@/lib/time";

type Props = {
  conversion: AdminUsersOutT["conversion"];
  className?: string;
};

/** Una etapa del embudo: label + valor + ancho relativo de la barra (0–1). */
type Stage = { key: string; label: string; value: number; ratio: number };

/**
 * F1.2 · Banda 2 (der) — Embudo de conversión (efímeros → registrados).
 *
 * Dos barras horizontales planas (token `--color-azul`, sin gradiente) con el
 * conteo `tabular-nums`, y la tasa de conversión como número grande
 * `text-display` con count-up. Honestidad de dato (regla #6): la conversión es
 * un **estimado** (no hay timestamp de conversión) — el schema lo clava con
 * `isEstimate: true` y la UI lo rotula con un marcador "estimado" + tooltip.
 * Client component por el count-up y el tooltip.
 */
export function ConversionFunnel({ conversion, className }: Props) {
  const tipId = useId();
  const [showTip, setShowTip] = useState(false);
  const animatedPct = useCountUp(conversion.conversion_pct);

  // El total efímero es la base del embudo (ancho 100%); registrados es el subset.
  const base = Math.max(1, conversion.ephemeral);
  const stages: Stage[] = [
    {
      key: "ephemeral",
      label: "Efímeros",
      value: conversion.ephemeral,
      ratio: 1,
    },
    {
      key: "registered",
      label: "Registrados",
      value: conversion.registered,
      ratio: Math.min(1, conversion.registered / base),
    },
  ];

  return (
    <Card className={cn("flex flex-col gap-6", className)}>
      <header className="relative flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <p className="text-caption text-[var(--color-ink-soft)]">Conversión</p>
          <h2 className="text-subtitle text-[var(--color-ink-deep)]">De efímero a registrado</h2>
        </div>
        {/* Marcador de honestidad de dato (regla #6): es un estimado. */}
        <button
          type="button"
          aria-describedby={tipId}
          aria-label="Conversión estimada — sin timestamp de conversión"
          className="shrink-0 rounded-[var(--radius-pill)] border border-[var(--color-border)] px-2 py-0.5 text-caption text-[var(--color-ink-soft)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
          onMouseEnter={() => setShowTip(true)}
          onMouseLeave={() => setShowTip(false)}
          onFocus={() => setShowTip(true)}
          onBlur={() => setShowTip(false)}
        >
          estimado
        </button>
        {showTip ? (
          <div
            id={tipId}
            role="tooltip"
            className="anim-fade-in absolute right-0 top-9 z-[var(--z-sticky)] w-56 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-glass)] px-3 py-2 shadow-soft"
          >
            <p className="text-body-sm text-[var(--color-ink-soft)]">
              Estimado — no hay timestamp de conversión; el ratio compara registrados sobre el total
              de cuentas efímeras del período.
            </p>
          </div>
        ) : null}
      </header>

      {/* Tasa de conversión como protagonista. */}
      <div className="flex flex-col gap-1">
        <p className="text-display tabular-nums text-[var(--color-ink-deep)]">
          {fmtPct(animatedPct)}
        </p>
        <p className="text-caption text-[var(--color-ink-soft)]">tasa de conversión (estimada)</p>
      </div>

      {/* Embudo: barras planas decrecientes. */}
      <ul className="flex flex-col gap-3">
        {stages.map((stage) => (
          <li key={stage.key} className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-body-sm text-[var(--color-ink)]">{stage.label}</span>
              <span className="text-body-sm tabular-nums text-[var(--color-ink-deep)]">
                {fmtInt(stage.value)}
              </span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]">
              <span
                className="block h-full origin-left rounded-[var(--radius-pill)] bg-[var(--color-azul)]"
                style={{ width: `${Math.round(stage.ratio * 100)}%` } as CSSProperties}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
