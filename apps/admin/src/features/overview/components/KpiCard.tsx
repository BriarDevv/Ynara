"use client";

import { type CSSProperties, useMemo } from "react";
import { Sparkline } from "@/components/charts/Sparkline";
import { Card } from "@/components/ui/Card";
import { Diamond } from "@/components/ui/Diamond";
import { useCountUp } from "@/hooks/useCountUp";
import { cn } from "@/lib/cn";
import { fmtDelta, fmtValue } from "@/lib/time";

/** Dirección del delta contra el período anterior (espeja `Delta` de Zod). */
type Direction = "up" | "down" | "flat";

type Props = {
  /** Etiqueta superior en `text-caption` uppercase (p.ej. "Usuarios totales"). */
  eyebrow: string;
  /** Valor del KPI. Numérico → count-up + formato; string → render directo. */
  value: number | string;
  /** Formato del valor cuando es numérico. Default `int`. */
  format?: "int" | "pct" | "ms" | "min";
  /** Variación contra el período anterior (pill con diamante direccional). */
  delta?: { pct: number; direction: Direction };
  /** Mini serie de tendencia opcional bajo el valor (sparkline azul plano). */
  spark?: number[];
  /** Índice para la cascada de entrada (`--stagger-index`, capado a 6). */
  staggerIndex?: number;
  /** Nota de honestidad de dato (proxy, estimado) en `text-caption` al pie. */
  note?: string;
  className?: string;
};

/**
 * Tarjeta de KPI del Overview (blueprint §2.3, §3 banda 2).
 *
 * Jerarquía editorial: eyebrow → valor grande (`text-display`, `tabular-nums`,
 * con count-up al montar) → pill de delta (`Diamond` rotado direccional: ▲ azul
 * de marca al subir, ▼ `--color-error` al bajar, neutro `ink-soft` plano) →
 * `Sparkline` opcional. Entra con `anim-stagger-up` (se neutraliza bajo
 * `html.motion-off`). Color 100% por token, cero hex, cero gradiente.
 */
export function KpiCard({
  eyebrow,
  value,
  format = "int",
  delta,
  spark,
  staggerIndex = 0,
  note,
  className,
}: Props) {
  const isNumeric = typeof value === "number";
  // El count-up solo aplica a valores numéricos; los string se muestran tal cual.
  const animated = useCountUp(isNumeric ? value : 0);
  const displayValue = isNumeric ? fmtValue(Math.round(animated), format) : value;

  const deltaStyle = useMemo(() => deltaColorFor(delta?.direction ?? "flat"), [delta?.direction]);

  return (
    <Card
      className={cn("anim-stagger-up flex flex-col gap-3", className)}
      style={{ "--stagger-index": Math.min(staggerIndex, 6) } as CSSProperties}
    >
      <p className="text-caption text-[var(--color-ink-soft)]">{eyebrow}</p>

      <div className="flex items-baseline justify-between gap-3">
        <span className="text-display tabular-nums leading-none text-[var(--color-ink-deep)]">
          {displayValue}
        </span>
        {delta ? (
          <span
            role="img"
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)] px-2.5 py-1 text-caption tabular-nums"
            style={{ color: deltaStyle.color }}
            aria-label={`Variación ${fmtDelta(delta.pct)} contra el período anterior`}
          >
            <Diamond size={7} color={deltaStyle.color} className={deltaStyle.rotation} />
            {fmtDelta(delta.pct)}
          </span>
        ) : null}
      </div>

      {spark && spark.length > 0 ? (
        <Sparkline data={spark} aria-label={`Tendencia de ${eyebrow.toLowerCase()}`} />
      ) : null}

      {note ? <p className="text-caption text-[var(--color-ink-muted)]">{note}</p> : null}
    </Card>
  );
}

/**
 * Color + giro del diamante por dirección del delta. El `Diamond` ya viene
 * rotado 45° (rombo); le sumamos un cuarto de vuelta para sugerir ▲/▼ sin
 * importar un ícono nuevo. Color plano por token: azul al subir, error al bajar,
 * ink-soft neutro al estar plano.
 */
function deltaColorFor(direction: Direction): { color: string; rotation: string } {
  switch (direction) {
    case "up":
      return { color: "var(--color-blue-flat)", rotation: "rotate-[225deg]" };
    case "down":
      return { color: "var(--color-error)", rotation: "rotate-[45deg]" };
    default:
      return { color: "var(--color-ink-soft)", rotation: "rotate-45" };
  }
}
