"use client";

import type { CSSProperties, ReactNode } from "react";
import { UsageHeatmap } from "@/components/charts/UsageHeatmap";
import { Card } from "@/components/ui/Card";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { cn } from "@/lib/cn";
import { useUsers } from "../hooks/useUsers";
import { ActivityKpis } from "./ActivityKpis";
import { ConversionFunnel } from "./ConversionFunnel";
import { SignupsTable } from "./SignupsTable";

/**
 * Composición client de Usuarios & Actividad (blueprint §3 F1.2).
 *
 * Vive separada de `page.tsx` (server) para que la ruta conserve `metadata` y el
 * default server-component mientras esta capa —que consume el hook `useUsers`
 * con el `range` global del topbar— sea la única client.
 *
 * Grilla 12-col por bandas (`gap-8`), reveal de page-load escalonado vía
 * `--stagger-index` por banda:
 *  1. `ActivityKpis` DAU/WAU/MAU (`col-span-12`, 3-up interno) — proxy por
 *     sesiones, rotulado "aprox.".
 *  2. `UsageHeatmap` (`col-span-7`, escala azul + `note` de proxy) +
 *     `ConversionFunnel` (`col-span-5`, rotulado "estimado").
 *  3. `SignupsTable` (`col-span-12`) — altas por día.
 *
 * Estados cuidados: skeleton de page-load, error editorial y empty (sin datos).
 */
export function UsersView() {
  const { data, isPending, isError, refetch } = useUsers();

  if (isPending) return <UsersSkeleton />;

  if (isError) {
    return (
      <EmptyStateCard
        title="No pudimos cargar la actividad de usuarios."
        hint="El endpoint /v1/admin/users no respondió. Reintentá en unos segundos."
        action={
          <button
            type="button"
            onClick={() => refetch()}
            className="rounded-[var(--radius-pill)] border border-[var(--color-border-strong)] px-4 py-2 text-button text-[var(--color-ink)] transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-bg-soft)]"
          >
            Reintentar
          </button>
        }
      />
    );
  }

  if (!data) {
    return (
      <EmptyStateCard
        title="Sin actividad en el rango."
        hint="No hay sesiones ni altas para la ventana temporal seleccionada."
      />
    );
  }

  const { activity, heatmap, conversion, signups } = data;

  return (
    <div className="grid grid-cols-12 gap-8">
      <Band span={12} index={0}>
        <ActivityKpis activity={activity} />
      </Band>

      <Band span={7} index={1}>
        <Card className="flex h-full flex-col gap-4">
          <header className="flex flex-col gap-1">
            <p className="text-caption text-[var(--color-ink-soft)]">Uso</p>
            <h2 className="text-subtitle text-[var(--color-ink-deep)]">Actividad diaria</h2>
          </header>
          <UsageHeatmap cells={heatmap} note="Actividad estimada por sesiones (no hay last_seen)" />
        </Card>
      </Band>

      <Band span={5} index={2}>
        <ConversionFunnel conversion={conversion} className="h-full" />
      </Band>

      <Band span={12} index={3}>
        <SignupsTable signups={signups} />
      </Band>
    </div>
  );
}

/** Mapeo de `span` a clase de columna (Tailwind necesita clases estáticas). */
const SPAN_CLASS: Record<5 | 7 | 12, string> = {
  5: "col-span-12 lg:col-span-5",
  7: "col-span-12 lg:col-span-7",
  12: "col-span-12",
};

/**
 * Banda de la grilla de 12 columnas con reveal escalonado de page-load: cada
 * banda entra con `.anim-stagger-up` y su `--stagger-index` (delay `index*40ms`,
 * neutralizado bajo reduced-motion por la cascada global).
 */
function Band({ span, index, children }: { span: 5 | 7 | 12; index: number; children: ReactNode }) {
  return (
    <div
      className={cn(SPAN_CLASS[span], "anim-stagger-up")}
      style={{ "--stagger-index": index } as CSSProperties}
    >
      {children}
    </div>
  );
}

/**
 * Skeleton de carga con la misma topología que la pantalla (3 tiles + heatmap +
 * funnel + tabla), para que el layout no salte al llegar el dato. Bloques planos
 * en `--color-bg-soft` con fade-in suave.
 */
function UsersSkeleton() {
  return (
    <div className="grid grid-cols-12 gap-8" aria-hidden>
      <div className="col-span-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="anim-fade-in h-44 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]"
          />
        ))}
      </div>
      <div className="anim-fade-in col-span-12 h-64 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-7" />
      <div className="anim-fade-in col-span-12 h-64 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-5" />
      <div className="anim-fade-in col-span-12 h-80 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
    </div>
  );
}
