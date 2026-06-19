"use client";

import { ConfidenceHistogram } from "@/components/charts/ConfidenceHistogram";
import { Card } from "@/components/ui/Card";
import type { AdminMoatOutT } from "@/features/moat/schemas";
import { cn } from "@/lib/cn";
import { fmtInt } from "@/lib/time";

type Props = {
  /** Bloque `procedural` del contrato: buckets de confidence + stale/healthy. */
  procedural: AdminMoatOutT["procedural"];
  className?: string;
};

/**
 * `ProceduralHealth` — salud de la capa procedural: distribución de `confidence`
 * (qué tan vigentes son los hábitos/rutinas que Ynara aprendió) + cuántas
 * perdieron vigencia (`stale`). Envuelve `ConfidenceHistogram`, que pinta los
 * buckets en azul plano y la barra de stale en `--color-error` (la única señal
 * "roja" del chart). Números con `tabular-nums`, cero gradiente.
 *
 * Honestidad de dato: el caption rotula qué cuenta como sano (confidence alta y
 * no-stale) para que el % no se lea fuera de contexto.
 */
export function ProceduralHealth({ procedural, className }: Props) {
  const { confidence_buckets, stale_count, healthy_count } = procedural;

  return (
    <Card className={cn("flex flex-col gap-5", className)}>
      <header className="flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Salud procedural</p>
        <h2 className="text-subtitle text-[var(--color-ink-deep)]">Confianza y vigencia</h2>
        <p className="text-body-sm text-[var(--color-ink-soft)]">
          <span className="tabular-nums text-[var(--color-ink-deep)]">{fmtInt(healthy_count)}</span>{" "}
          sanas ·{" "}
          <span className="tabular-nums text-[var(--color-error)]">{fmtInt(stale_count)}</span> sin
          vigencia.
        </p>
      </header>

      <ConfidenceHistogram
        buckets={confidence_buckets}
        staleCount={stale_count}
        healthyCount={healthy_count}
      />
    </Card>
  );
}
