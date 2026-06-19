"use client";

import type { CSSProperties } from "react";
import { Sparkline } from "@/components/charts/Sparkline";
import { Diamond } from "@/components/ui/Diamond";
import type { DeltaT } from "@/features/_shared/schemas";
import type { MoatLayerT } from "@/features/moat/schemas";
import { cn } from "@/lib/cn";
import { fmtDelta, fmtInt } from "@/lib/time";

/**
 * Color, etiqueta y descripción de cada capa del moat. El color sale de los
 * alias semánticos `--layer-*` (que apuntan a los tints oficiales) — plano, sin
 * gradiente. Misma fuente de verdad que `LineMultiSeries`/`MoatHealthHero`, así
 * el skyline y el chart de crecimiento hablan el mismo código de color.
 */
const LAYER_META: Record<MoatLayerT, { label: string; blurb: string; colorVar: string }> = {
  semantic: {
    label: "Semántica",
    blurb: "Hechos y preferencias que Ynara sabe de vos.",
    colorVar: "var(--layer-semantic)",
  },
  episodic: {
    label: "Episódica",
    blurb: "Lo que pasó: episodios consolidados.",
    colorVar: "var(--layer-episodic)",
  },
  procedural: {
    label: "Procedural",
    blurb: "Cómo hacer las cosas: hábitos y rutinas.",
    colorVar: "var(--layer-procedural)",
  },
};

/** Color del texto del delta según dirección (verde de marca = azul; baja = error). */
const DELTA_COLOR: Record<DeltaT["direction"], string> = {
  up: "var(--color-azul)",
  down: "var(--color-error)",
  flat: "var(--color-ink-soft)",
};

/** Glifo del delta. Diamante rotado como flecha sutil (lenguaje del DS). */
const DELTA_GLYPH: Record<DeltaT["direction"], string> = {
  up: "▲",
  down: "▼",
  flat: "◆",
};

type Props = {
  /** Capa que representa esta torre. */
  layer: MoatLayerT;
  /** Cantidad total de memorias en la capa. */
  count: number;
  /** Variación contra el período anterior. */
  delta?: DeltaT;
  /**
   * Altura relativa de la barra (0–1), proporcional al count contra la capa
   * más grande. La calcula el contenedor (`page.tsx`) para que las 3 torres
   * compartan escala y formen el skyline.
   */
  relativeHeight: number;
  /** Serie corta para la sparkline de tendencia (opcional). */
  spark?: number[];
  /** Índice de stagger para la entrada escalonada. */
  staggerIndex?: number;
  className?: string;
};

/**
 * `MoatTower` — una columna del moat. Ícono de capa (diamante teñido) + nombre +
 * count grande `tabular-nums` + delta + barra vertical de altura proporcional
 * (plana, color de capa) + sparkline opcional. Tres juntas = el "skyline" del
 * moat: se lee de un vistazo qué capa pesa más y cómo crece cada una.
 *
 * Color 100% por token (`--layer-*`), cero gradiente, números con `tabular-nums`.
 */
export function MoatTower({
  layer,
  count,
  delta,
  relativeHeight,
  spark,
  staggerIndex = 0,
  className,
}: Props) {
  const meta = LAYER_META[layer];
  // Mínimo visible para que ninguna torre desaparezca aunque la capa sea chica.
  const barHeightPct = Math.max(6, Math.min(100, relativeHeight * 100));

  return (
    <div
      className={cn(
        "anim-stagger-up flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-5",
        className,
      )}
      style={{ "--stagger-index": staggerIndex } as CSSProperties}
    >
      {/* Encabezado: ícono de capa + nombre + blurb. */}
      <div className="flex items-start gap-3">
        <Diamond size={12} color={meta.colorVar} className="mt-1" />
        <div className="flex flex-col gap-1">
          <h3 className="text-subtitle text-[var(--color-ink-deep)]">{meta.label}</h3>
          <p className="text-body-sm text-[var(--color-ink-soft)]">{meta.blurb}</p>
        </div>
      </div>

      {/* Count grande + delta. */}
      <div className="flex items-end justify-between gap-3">
        <span className="text-display tabular-nums text-[var(--color-ink-deep)]">
          {fmtInt(count)}
        </span>
        {delta ? (
          <span
            className="flex items-center gap-1 text-body-sm tabular-nums"
            style={{ color: DELTA_COLOR[delta.direction] }}
          >
            <span aria-hidden className="text-[0.625rem] leading-none">
              {DELTA_GLYPH[delta.direction]}
            </span>
            {fmtDelta(delta.pct)}
          </span>
        ) : null}
      </div>

      {/* Barra vertical proporcional (la "altura" de la torre en el skyline). */}
      <div
        className="flex h-28 items-end rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)] p-1.5"
        aria-hidden
      >
        <div
          className="w-full origin-bottom rounded-[var(--radius-sm)] transition-[height] duration-[var(--duration-slow)] ease-[var(--ease-out-soft)]"
          style={{ height: `${barHeightPct}%`, backgroundColor: meta.colorVar }}
        />
      </div>

      {/* Tendencia (sparkline) si hay serie. */}
      {spark && spark.length > 1 ? (
        <Sparkline data={spark} aria-label={`Tendencia de la capa ${meta.label}`} />
      ) : null}
    </div>
  );
}
