"use client";

import type { CSSProperties } from "react";
import { PerimeterBadge } from "@/components/shell/PerimeterBadge";
import { LivingField } from "@/components/ui/LivingField";
import type { OverviewPerimeterT } from "@/features/overview/schemas";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/relativeTime";
import { RANGE_HUMAN } from "@/lib/time";
import type { RangeId } from "@/stores/range";

type Props = {
  /** Estado del perímetro (status + detalle + timestamp del último chequeo). */
  perimeter: OverviewPerimeterT;
  /** Rango temporal activo (se rotula en el caption del campo vivo). */
  range: RangeId;
  /** Índice para la cascada de entrada de las bandas del main. */
  staggerIndex?: number;
  className?: string;
};

/**
 * Banda hero del Overview (blueprint §3 banda 1).
 *
 * Izquierda: `PerimeterBadge variant="hero"` con el estado de soberanía en
 * `text-title` — la firma de la pantalla. Derecha: `LivingField variant="depth"
 * density="sutil"`, la **única atmósfera animada** de la vista, con el rango
 * activo rotulado en caption. El contenedor es `relative isolate` (requisito de
 * montaje del campo vivo) y el campo va detrás del contenido en `-z-field`.
 *
 * Honestidad de dato: muestra cuándo se verificó el perímetro por última vez
 * (`checkedAt`, en tiempo relativo) para que el operador sepa la frescura del
 * estado, no solo el color.
 */
export function StatusHero({ perimeter, range, staggerIndex = 0, className }: Props) {
  const checkedAtMs = Date.parse(perimeter.checked_at);
  const checkedLabel = Number.isFinite(checkedAtMs) ? relativeTime(checkedAtMs) : null;

  return (
    <section
      className={cn(
        "anim-stagger-up relative isolate overflow-hidden rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-bg)] shadow-soft",
        className,
      )}
      style={{ "--stagger-index": staggerIndex } as CSSProperties}
      aria-label="Estado del perímetro de soberanía"
    >
      <LivingField variant="depth" density="sutil" />

      <div className="relative z-[var(--z-base)] flex flex-col gap-8 p-8 md:flex-row md:items-end md:justify-between">
        <PerimeterBadge
          variant="hero"
          status={perimeter.status}
          detail={perimeter.detail ?? undefined}
        />

        <div className="flex flex-col gap-1 md:items-end md:text-right">
          <span className="text-caption text-[var(--color-ink-soft)]">Ventana activa</span>
          <span className="text-subtitle text-[var(--color-ink-deep)]">{RANGE_HUMAN[range]}</span>
          {checkedLabel ? (
            <span className="text-caption tabular-nums text-[var(--color-ink-muted)]">
              Verificado {checkedLabel}
            </span>
          ) : null}
        </div>
      </div>
    </section>
  );
}
