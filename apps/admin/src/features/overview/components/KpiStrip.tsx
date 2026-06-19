"use client";

import type { AdminOverviewOutT } from "@/features/overview/schemas";
import { cn } from "@/lib/cn";
import { KpiCard } from "./KpiCard";

type Props = {
  /** Bloque `kpis` del contrato del Overview (§4.1). */
  kpis: AdminOverviewOutT["kpis"];
  /** Offset de stagger para encadenar la cascada con la banda que la precede. */
  baseStagger?: number;
  className?: string;
};

/**
 * Tira de 4 KPIs del Overview (blueprint §3 banda 2): usuarios totales, sesiones
 * en el rango (con sparkline), memorias consolidadas (suma de las 3 capas del
 * moat) y eventos de audit en el rango. Grilla de 4 en `lg`, 2 en `sm`, 1 en
 * mobile. Cascada de stagger anidada: cada `KpiCard` re-staggerea con su propio
 * índice (delay creciente izq→der) para que la tira "se arme sola" en page-load.
 *
 * tabular-nums-guard: n/a — esta tira no pinta dígitos directamente; cada número
 * lo renderiza `KpiCard` (que sí lleva `tabular-nums`). Acá solo se pasan los
 * `format="int"` como props de composición.
 */
export function KpiStrip({ kpis, baseStagger = 0, className }: Props) {
  return (
    <div className={cn("grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4", className)}>
      <KpiCard
        eyebrow="Usuarios totales"
        value={kpis.users_total.value}
        format="int"
        delta={kpis.users_total.delta}
        staggerIndex={baseStagger}
      />
      <KpiCard
        eyebrow="Sesiones en el rango"
        value={kpis.sessions.value}
        format="int"
        delta={kpis.sessions.delta}
        spark={kpis.sessions.spark}
        staggerIndex={baseStagger + 1}
      />
      <KpiCard
        eyebrow="Memorias consolidadas"
        value={kpis.memories.value}
        format="int"
        delta={kpis.memories.delta}
        staggerIndex={baseStagger + 2}
        note="Suma de las 3 capas del moat"
      />
      <KpiCard
        eyebrow="Eventos de audit"
        value={kpis.audit_events.value}
        format="int"
        delta={kpis.audit_events.delta}
        staggerIndex={baseStagger + 3}
      />
    </div>
  );
}
