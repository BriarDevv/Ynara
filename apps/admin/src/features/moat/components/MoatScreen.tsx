"use client";

import type { CSSProperties, ReactNode } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { useMoat } from "@/features/moat/hooks/useMoat";
import type { MoatLayerT } from "@/features/moat/schemas";
import { cn } from "@/lib/cn";
import { useRangeStore } from "@/stores/range";
import { ConsolidationHeartbeat } from "./ConsolidationHeartbeat";
import { LayerGrowth } from "./LayerGrowth";
import { MoatHealthHero } from "./MoatHealthHero";
import { MoatTower } from "./MoatTower";
import { ProceduralHealth } from "./ProceduralHealth";

/** Banda con stagger de entrada (la página "se arma sola" en page-load, §5). */
function Band({
  index,
  className,
  children,
}: {
  index: number;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn("anim-stagger-up", className)}
      style={{ "--stagger-index": index } as CSSProperties}
    >
      {children}
    </div>
  );
}

/** Skeleton de carga acorde a la grilla de la pantalla (banda hero + bandas). */
function MoatSkeleton() {
  return (
    <div role="status" aria-label="Cargando salud del moat" className="flex flex-col gap-8">
      <div className="anim-pulse-soft h-72 rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="anim-pulse-soft h-64 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]"
          />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="anim-pulse-soft h-80 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-8" />
        <div className="anim-pulse-soft h-80 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-4" />
      </div>
      <div className="anim-pulse-soft h-56 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
    </div>
  );
}

/** Orden de capas (externo→interno = skyline de mayor a menor en el fixture). */
const LAYER_ORDER: MoatLayerT[] = ["semantic", "episodic", "procedural"];

/**
 * `MoatScreen` — cuerpo client de la pantalla F1.4 (Salud del Moat). Lee el
 * rango global, hace `useMoat(range)` y compone la grilla de bandas:
 *
 *  1. Hero "latido de la memoria" (`MoatHealthHero`).
 *  2. Skyline: 3 `MoatTower` (una por capa) en altura proporcional compartida.
 *  3. Crecimiento por capa (`LayerGrowth`) + salud procedural (`ProceduralHealth`).
 *  4. Pulso de consolidación (`ConsolidationHeartbeat`).
 *
 * Estados cuidados: loading (skeleton acorde a la grilla), error (empty con
 * reintento), data vacía (counts en cero → empty editorial). Entrada con
 * `anim-stagger-up` escalonado por banda. Cero gradiente fuera del campo vivo,
 * cero hex, `tabular-nums` en todo número.
 */
export function MoatScreen() {
  const range = useRangeStore((s) => s.range);
  const { data, isPending, isError, refetch } = useMoat(range);

  if (isPending) return <MoatSkeleton />;

  if (isError || !data) {
    return (
      <EmptyStateCard
        title="No pudimos leer la salud del moat."
        hint="Reintentá en unos segundos."
        action={
          <button
            type="button"
            onClick={() => refetch()}
            className="text-button text-[var(--color-accent)] underline-offset-4 hover:underline"
          >
            Reintentar
          </button>
        }
      />
    );
  }

  const { counts, deltas, growth, procedural, consolidation } = data;

  const totalMemories = counts.semantic + counts.episodic + counts.procedural;
  if (totalMemories === 0) {
    return (
      <EmptyStateCard
        title="El moat todavía está vacío."
        hint="Cuando Ynara empiece a recordar, las tres capas van a poblarse acá."
      />
    );
  }

  // Altura relativa del skyline: la capa más grande define el 100%.
  const maxCount = Math.max(counts.semantic, counts.episodic, counts.procedural, 1);
  // Sparkline por torre: la serie de crecimiento de su capa.
  const sparkByLayer = new Map<MoatLayerT, number[]>(
    growth.map((g) => [g.key, g.points.map((p) => p.value)]),
  );

  return (
    <div className="flex flex-col gap-8">
      {/* Banda 1 — Hero "latido de la memoria". */}
      <Band index={0}>
        <MoatHealthHero counts={counts} backlog={consolidation.backlog} />
      </Band>

      {/* Banda 2 — Skyline: 3 torres de capa. */}
      <Band index={1}>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {LAYER_ORDER.map((layer, i) => (
            <MoatTower
              key={layer}
              layer={layer}
              count={counts[layer]}
              delta={deltas[layer]}
              relativeHeight={counts[layer] / maxCount}
              spark={sparkByLayer.get(layer)}
              staggerIndex={i}
            />
          ))}
        </div>
      </Band>

      {/* Banda 3 — Crecimiento por capa + salud procedural. */}
      <Band index={2}>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <LayerGrowth growth={growth} className="lg:col-span-8" />
          <ProceduralHealth procedural={procedural} className="lg:col-span-4" />
        </div>
      </Band>

      {/* Banda 4 — Pulso de consolidación. */}
      <Band index={3}>
        <ConsolidationHeartbeat consolidation={consolidation} />
      </Band>
    </div>
  );
}
