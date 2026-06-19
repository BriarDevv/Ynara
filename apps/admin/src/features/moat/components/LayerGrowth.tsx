"use client";

import { LineMultiSeries } from "@/components/charts/LineMultiSeries";
import { Card } from "@/components/ui/Card";
import type { AdminMoatOutT } from "@/features/moat/schemas";
import { cn } from "@/lib/cn";

type Props = {
  /** Series de crecimiento por capa (del contrato `AdminMoatOut.growth`). */
  growth: AdminMoatOutT["growth"];
  className?: string;
};

/**
 * `LayerGrowth` — crecimiento acumulado de las 3 capas de memoria en el rango.
 * Envuelve `LineMultiSeries` (3 líneas planas, una por capa, con su color
 * `--layer-*`) en una `Card` con título editorial. La leyenda del chart ya
 * documenta el código de color de capa.
 *
 * Mapea el shape del contrato (`{ key, points }[]`) directo a la prop `series`
 * del chart — las claves coinciden 1:1 con `LayerKey`.
 */
export function LayerGrowth({ growth, className }: Props) {
  return (
    <Card className={cn("flex flex-col gap-5", className)}>
      <header className="flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Crecimiento</p>
        <h2 className="text-subtitle text-[var(--color-ink-deep)]">El moat por capa</h2>
        <p className="text-body-sm text-[var(--color-ink-soft)]">
          Memorias acumuladas en cada capa a lo largo del rango.
        </p>
      </header>

      <LineMultiSeries series={growth} />
    </Card>
  );
}
