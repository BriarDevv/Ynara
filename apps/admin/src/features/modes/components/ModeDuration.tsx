import { ModeBarChart } from "@/components/charts/ModeBarChart";
import { Card } from "@/components/ui/Card";
import { MODE_BY_ID } from "@/components/ui/modes";
import type { AdminModesOutT } from "@/features/modes/schemas";
import { fmtInt } from "@/lib/time";

type Props = {
  /** `duration` del contrato: media en minutos + cerradas/abiertas por modo. */
  duration: AdminModesOutT["duration"];
  className?: string;
};

/**
 * F1.3 · Banda 2 — Duración media por modo.
 *
 * Tarjeta que envuelve `<ModeBarChart valueFormat="min"/>` (barras horizontales
 * con el `fillVar` del modo). El valor es la duración media en minutos.
 *
 * Honestidad de dato (regla #6): la media solo cubre **sesiones cerradas**
 * (`ended_at IS NOT NULL`). Rotulamos en el caption cuántas cerradas alimentan
 * el promedio y cuántas quedaron abiertas (excluidas), para no insinuar que el
 * promedio mide sesiones en curso.
 *
 * Server component: proyección pura de datos al chart.
 */
export function ModeDuration({ duration, className }: Props) {
  // El bar chart quiere `{ mode, value, label }`; usamos `avg_minutes → value`.
  const data = duration.map((d) => ({
    mode: d.mode,
    value: d.avg_minutes,
    label: MODE_BY_ID[d.mode].label,
  }));

  const closed = duration.reduce((sum, d) => sum + d.closed_sessions, 0);
  const open = duration.reduce((sum, d) => sum + d.open_sessions, 0);

  return (
    <Card className={className}>
      <header className="mb-6 flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Duración media</p>
        <h2 className="text-subtitle text-[var(--color-ink-deep)]">Cuánto dura cada modo</h2>
      </header>

      <ModeBarChart data={data} valueFormat="min" />

      {/* Honestidad de dato: alcance del promedio (cerradas vs abiertas). */}
      <p className="mt-5 text-body-sm text-[var(--color-ink-soft)]">
        Media calculada sobre{" "}
        <span className="tabular-nums text-[var(--color-ink)]">{fmtInt(closed)}</span> sesiones
        cerradas; <span className="tabular-nums text-[var(--color-ink)]">{fmtInt(open)}</span>{" "}
        abiertas quedan fuera del promedio.
      </p>
    </Card>
  );
}
