import type { CSSProperties } from "react";
import { Card } from "@/components/ui/Card";
import { MODES } from "@/components/ui/modes";
import type { AdminModesOutT } from "@/features/modes/schemas";
import { cn } from "@/lib/cn";
import { fmtInt, fmtMin, fmtPct } from "@/lib/time";

type Props = {
  mix: AdminModesOutT["mix"];
  duration: AdminModesOutT["duration"];
  className?: string;
};

/**
 * F1.3 · Banda 3 — Tira de los 5 modos. **Acá cantan los 5 tints oficiales.**
 *
 * Una card por modo (siempre las 5, en el orden canónico de `MODES`), con:
 *   - barra de acento superior de 3px con el `tintVar` del modo (el color que
 *     identifica al modo en todo el producto),
 *   - nombre `text-subtitle` + blurb canónico del descriptor de modo,
 *   - dos métricas `tabular-nums`: sesiones (+ % del mix) y duración media.
 *
 * Iteramos sobre `MODES` (no sobre los datos) para garantizar que las 5 tarjetas
 * aparezcan aunque un modo no tenga sesiones en el rango (cae a 0). Cada card
 * entra con `anim-stagger-up` (cascada izq→der; se neutraliza bajo motion-off).
 *
 * Server component: composición pura de datos + tokens, sin estado.
 */
export function ModeCardStrip({ mix, duration, className }: Props) {
  // Índices por modo para lookup O(1) sin asumir orden de los arrays del contrato.
  const mixByMode = new Map(mix.map((m) => [m.mode, m]));
  const durationByMode = new Map(duration.map((d) => [d.mode, d]));

  return (
    <ul
      className={cn(
        "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5",
        className,
      )}
    >
      {MODES.map((mode, i) => {
        const m = mixByMode.get(mode.id);
        const d = durationByMode.get(mode.id);
        const sessions = m?.sessions ?? 0;
        const pct = m?.pct ?? 0;
        const avgMinutes = d?.avg_minutes ?? 0;

        return (
          <li
            key={mode.id}
            className="anim-stagger-up"
            style={{ "--stagger-index": Math.min(i, 6) } as CSSProperties}
          >
            <Card className="relative h-full overflow-hidden pt-7">
              {/* Barra de acento superior con el tint del modo (el tint canta). */}
              <span
                aria-hidden
                className="absolute inset-x-0 top-0 h-[3px]"
                style={{ backgroundColor: mode.tintVar }}
              />

              <h3 className="text-subtitle text-[var(--color-ink-deep)]">{mode.label}</h3>
              <p className="mt-1 text-body-sm text-[var(--color-ink-soft)]">{mode.blurb}</p>

              <dl className="mt-5 flex flex-col gap-3">
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-caption text-[var(--color-ink-soft)]">Sesiones</dt>
                  <dd className="text-body-sm tabular-nums text-[var(--color-ink-deep)]">
                    {fmtInt(sessions)}
                    <span className="ml-2 text-[var(--color-ink-muted)]">{fmtPct(pct)}</span>
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-caption text-[var(--color-ink-soft)]">Duración media</dt>
                  <dd className="text-body-sm tabular-nums text-[var(--color-ink-deep)]">
                    {fmtMin(avgMinutes)}
                  </dd>
                </div>
              </dl>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
