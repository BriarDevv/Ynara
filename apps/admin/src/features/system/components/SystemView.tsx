"use client";

import type { CSSProperties, ReactNode } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { cn } from "@/lib/cn";
import { useSystem } from "../hooks/useSystem";
import { ProdGuardBanner } from "./ProdGuardBanner";
import { RuntimeInventory } from "./RuntimeInventory";
import { StatusCard } from "./StatusCard";

/**
 * Composición client de System Health (blueprint §3 F1.6).
 *
 * Vive separada de `page.tsx` (server) para que la ruta conserve `metadata` y el
 * default server-component mientras esta capa —que consume el hook `useSystem`—
 * sea la única client. NO lleva `range`: System es runtime/config, foto única.
 *
 * Grilla 12-col por bandas (`gap-8`), reveal de page-load escalonado vía
 * `--stagger-index` por banda:
 *  1. `ProdGuardBanner` (`col-span-12`) — lo primero que ve el operador.
 *  2. Dos `StatusCard` (`col-span-6` c/u) — Postgres + Redis.
 *  3. `RuntimeInventory` (`col-span-12`) — config no sensible.
 *
 * Estados cuidados: skeleton de page-load, error editorial y empty (sin datos).
 */
export function SystemView() {
  const { data, isPending, isError, refetch } = useSystem();

  if (isPending) return <SystemSkeleton />;

  if (isError) {
    return (
      <EmptyStateCard
        title="No pudimos leer el estado del sistema."
        hint="El health-check de runtime no respondió. Reintentá en unos segundos."
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
        title="Sin datos de runtime."
        hint="El endpoint /v1/admin/system devolvió vacío."
      />
    );
  }

  const { guard, services, runtime } = data;

  return (
    <div className="grid grid-cols-12 gap-8">
      <Band span={12} index={0}>
        <ProdGuardBanner
          guardActive={guard.active}
          dbTarget={guard.db_target}
          isProdInDev={guard.is_prod_in_dev}
        />
      </Band>

      <Band span={6} index={1}>
        <StatusCard
          service="postgres"
          up={services.postgres.up}
          latencyMs={services.postgres.latency_ms}
          detail={services.postgres.detail}
          checkedAt={services.postgres.checked_at}
        />
      </Band>

      <Band span={6} index={2}>
        <StatusCard
          service="redis"
          up={services.redis.up}
          latencyMs={services.redis.latency_ms}
          detail={services.redis.detail}
          checkedAt={services.redis.checked_at}
        />
      </Band>

      <Band span={12} index={3}>
        <RuntimeInventory
          models={runtime.models}
          modes={runtime.modes}
          schemaHead={runtime.schema_head}
          embedder={runtime.embedder}
          reranker={runtime.reranker}
          buildVersion={runtime.build_version}
        />
      </Band>
    </div>
  );
}

/** Mapeo de `span` a clase de columna (Tailwind necesita clases estáticas). */
const SPAN_CLASS: Record<6 | 12, string> = {
  6: "col-span-12 lg:col-span-6",
  12: "col-span-12",
};

/**
 * Banda de la grilla de 12 columnas con reveal escalonado de page-load: cada
 * banda entra con `.anim-stagger-up` y su `--stagger-index` (delay `index*40ms`,
 * neutralizado bajo reduced-motion por la cascada global).
 */
function Band({ span, index, children }: { span: 6 | 12; index: number; children: ReactNode }) {
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
 * Skeleton de carga con la misma topología que la pantalla (banner + 2 cards +
 * inventario), para que el layout no salte al llegar el dato. Bloques planos en
 * `--color-bg-soft` con un fade-in suave (sin pulso para no competir con los
 * latidos de estado).
 */
function SystemSkeleton() {
  return (
    <div className="grid grid-cols-12 gap-8" aria-hidden>
      <div className="anim-fade-in col-span-12 h-24 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
      <div className="anim-fade-in col-span-12 h-48 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-6" />
      <div className="anim-fade-in col-span-12 h-48 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-6" />
      <div className="anim-fade-in col-span-12 h-72 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
    </div>
  );
}
