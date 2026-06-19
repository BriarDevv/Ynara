"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { AreaTimeSeries } from "@/components/charts/AreaTimeSeries";
import { ModeBarChart } from "@/components/charts/ModeBarChart";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { MODE_BY_ID } from "@/components/ui/modes";
import { AuditPreview } from "@/features/overview/components/AuditPreview";
import { KpiStrip } from "@/features/overview/components/KpiStrip";
import { StatusHero } from "@/features/overview/components/StatusHero";
import { useOverview } from "@/features/overview/hooks/useOverview";
import { type RangeId, useRangeStore } from "@/stores/range";

/**
 * F1.1 — Overview · ruta "/" (blueprint §3 F1.1).
 *
 * Pantalla de entrada del panel: estado del perímetro de soberanía + 4 KPIs de
 * producto + serie de sesiones/día + mix de modos compacto + preview de la
 * auditoría reciente, todo en el rango temporal global del topbar.
 *
 * Es client component porque consume `useRangeStore` y `useOverview` (TanStack
 * Query con `Schema.parse`). Composición en bandas sobre una grilla de 12
 * columnas, separadas `gap-8`; cada banda entra con `anim-stagger-up` (cascada
 * de page-load "la página se arma sola"). Estados de carga (skeleton), error y
 * vacío resueltos en la propia pantalla.
 */
export default function OverviewPage() {
  const range = useRangeStore((s) => s.range);
  const query = useOverview(range);

  return (
    <section className="flex flex-col gap-8">
      <PageHeader />

      {query.isLoading ? <OverviewSkeleton /> : null}

      {query.error ? (
        <Card className="flex flex-col items-start gap-3">
          <p className="text-subtitle text-[var(--color-ink)]">No pudimos cargar el Overview</p>
          <p className="max-w-[var(--measure-prose)] text-body-sm text-[var(--color-ink-soft)]">
            Hubo un problema al pedir los datos del panel en este rango. Probá de nuevo.
          </p>
          <Button variant="secondary" onClick={() => query.refetch()} disabled={query.isFetching}>
            {query.isFetching ? "Reintentando…" : "Reintentar"}
          </Button>
        </Card>
      ) : null}

      {query.data ? <OverviewBands data={query.data} range={range} /> : null}
    </section>
  );
}

/** Encabezado editorial (eyebrow + título + bajada). */
function PageHeader() {
  return (
    <header className="flex flex-col gap-2">
      <p className="text-caption text-[var(--color-ink-soft)]">Panel · Soberanía</p>
      <h1 className="text-display text-[var(--color-ink-deep)]">Overview</h1>
      <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
        Estado del perímetro, KPIs de producto y un vistazo a la auditoría reciente, en el rango
        temporal elegido.
      </p>
    </header>
  );
}

/** Composición real en bandas sobre la grilla de 12 columnas (page-load). */
function OverviewBands({
  data,
  range,
}: {
  data: NonNullable<ReturnType<typeof useOverview>["data"]>;
  range: RangeId;
}) {
  // El mix viene como { mode, value }; el ModeBarChart pide además el label
  // canónico del modo (para el ModeChip de cada fila).
  const modeBars = data.mode_mix.map((m) => ({
    mode: m.mode,
    value: m.value,
    label: MODE_BY_ID[m.mode].label,
  }));

  return (
    <div className="grid grid-cols-12 gap-8">
      {/* Banda 1 — Hero de perímetro + campo vivo. */}
      <div className="col-span-12">
        <StatusHero perimeter={data.perimeter} range={range} staggerIndex={0} />
      </div>

      {/* Banda 2 — Tira de 4 KPIs (cascada anidada). */}
      <div
        className="anim-stagger-up col-span-12"
        style={{ "--stagger-index": 1 } as CSSProperties}
      >
        <KpiStrip kpis={data.kpis} baseStagger={1} />
      </div>

      {/* Banda 3 — Serie de sesiones/día + mix de modos compacto. */}
      <div
        className="anim-stagger-up col-span-12 lg:col-span-8"
        style={{ "--stagger-index": 2 } as CSSProperties}
      >
        <Card className="flex h-full flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-subtitle text-[var(--color-ink-deep)]">Sesiones por día</h2>
            <p className="text-caption text-[var(--color-ink-muted)]">
              Conteo diario en el rango activo.
            </p>
          </div>
          <AreaTimeSeries points={data.sessions_series} valueLabel="Sesiones" />
        </Card>
      </div>

      <div
        className="anim-stagger-up col-span-12 lg:col-span-4"
        style={{ "--stagger-index": 3 } as CSSProperties}
      >
        <Card className="flex h-full flex-col gap-4">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="text-subtitle text-[var(--color-ink-deep)]">Mix de modos</h2>
            <Link
              href="/modos"
              className="shrink-0 text-body-sm text-[var(--color-accent)] underline underline-offset-4 decoration-[var(--color-ink-faint)] hover:decoration-[var(--color-accent)]"
            >
              Detalle
            </Link>
          </div>
          <ModeBarChart data={modeBars} valueFormat="int" />
        </Card>
      </div>

      {/* Banda 4 — Preview de auditoría reciente. */}
      <div
        className="anim-stagger-up col-span-12"
        style={{ "--stagger-index": 4 } as CSSProperties}
      >
        <AuditPreview rows={data.audit_preview} />
      </div>
    </div>
  );
}

/**
 * Skeleton específico del Overview mientras carga el primer dato del rango.
 * Espeja la grilla real (hero ancho, 4 KPIs, chart + mix, preview) para que el
 * layout no salte al llegar los datos. Shimmer por opacidad (`anim-pulse-soft`,
 * GPU-safe, se neutraliza bajo reduced-motion).
 */
function OverviewSkeleton() {
  return (
    <div role="status" aria-label="Cargando Overview" className="grid grid-cols-12 gap-8">
      <div className="anim-pulse-soft col-span-12 h-40 rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
      <div className="col-span-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="anim-pulse-soft h-32 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]"
          />
        ))}
      </div>
      <div className="anim-pulse-soft col-span-12 h-72 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-8" />
      <div className="anim-pulse-soft col-span-12 h-72 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-4" />
      <div className="anim-pulse-soft col-span-12 h-64 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
    </div>
  );
}
