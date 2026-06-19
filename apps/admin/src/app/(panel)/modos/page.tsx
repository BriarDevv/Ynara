"use client";

import type { CSSProperties } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { ModeCardStrip } from "@/features/modes/components/ModeCardStrip";
import { ModeDuration } from "@/features/modes/components/ModeDuration";
import { ModeMix } from "@/features/modes/components/ModeMix";
import { useModes } from "@/features/modes/hooks/useModes";
import { RANGE_HUMAN } from "@/lib/time";
import { useRangeStore } from "@/stores/range";

/**
 * F1.3 — Modos · ruta "/modos" (blueprint §3).
 *
 * Composición real sobre `useModes()` (lee el rango global del chrome). Grilla
 * de 12 columnas por bandas con `gap-8`:
 *   - Banda 1 (`col-span-5`): `<ModeMix/>` con `<ModeDonut/>` (slices `fillVar`).
 *   - Banda 2 (`col-span-7`): `<ModeDuration/>` con `<ModeBarChart valueFormat="min"/>`.
 *   - Banda 3 (`col-span-12`): `<ModeCardStrip/>` — 5 cards con el tint por modo.
 *
 * Page-load escalonado: cada banda entra con `.anim-stagger-up` (delay por
 * `--stagger-index`), neutralizado bajo `html.motion-off` / reduced-motion. Es
 * client component porque el hook depende del store de rango + React Query.
 *
 * Estados cuidados: skeleton de bandas en loading, `EmptyStateCard` si no hay
 * sesiones en el rango, y mensaje de error sobrio si el fetch/parse falla.
 */
export default function ModosPage() {
  const range = useRangeStore((s) => s.range);
  const { data, isPending, isError } = useModes();

  return (
    <section className="flex flex-col gap-8">
      <header
        className="anim-stagger-up flex flex-col gap-2"
        style={{ "--stagger-index": 0 } as CSSProperties}
      >
        <p className="text-caption text-[var(--color-ink-soft)]">Producto</p>
        <h1 className="text-display text-[var(--color-ink-deep)]">Modos</h1>
        <p className="max-w-[var(--measure-prose)] text-body text-[var(--color-ink-soft)]">
          Mix de sesiones por modo y duración media (sólo sesiones cerradas), con los cinco tints
          oficiales de marca. {RANGE_HUMAN[range]}.
        </p>
      </header>

      {isPending ? (
        <ModosSkeleton />
      ) : isError ? (
        <EmptyStateCard
          title="No pudimos cargar los modos."
          hint="Reintentá cambiando el rango o recargá la pantalla."
        />
      ) : data.total === 0 ? (
        <EmptyStateCard
          title="Sin sesiones en este rango."
          hint="Ampliá la ventana temporal para ver el reparto por modo."
        />
      ) : (
        <>
          {/* Bandas 1 + 2: mix (5 col) + duración (7 col). */}
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
            <div
              className="anim-stagger-up lg:col-span-5"
              style={{ "--stagger-index": 1 } as CSSProperties}
            >
              <ModeMix mix={data.mix} total={data.total} className="h-full" />
            </div>
            <div
              className="anim-stagger-up lg:col-span-7"
              style={{ "--stagger-index": 2 } as CSSProperties}
            >
              <ModeDuration duration={data.duration} className="h-full" />
            </div>
          </div>

          {/* Banda 3: tira de los 5 modos (acá cantan los tints). */}
          <div className="anim-stagger-up" style={{ "--stagger-index": 3 } as CSSProperties}>
            <ModeCardStrip mix={data.mix} duration={data.duration} />
          </div>
        </>
      )}
    </section>
  );
}

/**
 * Skeleton de la pantalla de Modos: dos bandas (mix + duración) y la tira de 5
 * cards, con el mismo layout que el contenido real para evitar saltos. Shimmer
 * `anim-pulse-soft` (opacidad pura, GPU-safe, se neutraliza bajo reduced-motion).
 */
function ModosSkeleton() {
  return (
    <div role="status" aria-label="Cargando modos" className="flex flex-col gap-8">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        <div className="anim-pulse-soft h-72 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-5" />
        <div className="anim-pulse-soft h-72 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] lg:col-span-7" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="anim-pulse-soft h-44 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]"
          />
        ))}
      </div>
    </div>
  );
}
