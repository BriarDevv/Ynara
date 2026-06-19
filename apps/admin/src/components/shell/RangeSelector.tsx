"use client";

import { cn } from "@/lib/cn";
import { RANGE_IDS, type RangeId, useRangeStore } from "@/stores/range";

/**
 * Segmented control del rango temporal global (blueprint §2.1): `24h · 7d · 30d
 * · 90d`. Vive en el topbar y escribe `useRangeStore`; todas las pantallas
 * (salvo System Health) lo leen como query param. El activo lleva un dot azul
 * plano + fondo suave (sin gradiente). Implementado con `radiogroup` para que el
 * lector de pantalla anuncie las 4 opciones como un grupo.
 */
const RANGE_LABEL: Record<RangeId, string> = {
  "24h": "24h",
  "7d": "7d",
  "30d": "30d",
  "90d": "90d",
};

export function RangeSelector() {
  const range = useRangeStore((s) => s.range);
  const setRange = useRangeStore((s) => s.setRange);

  return (
    <div
      role="radiogroup"
      aria-label="Rango temporal"
      className="inline-flex items-center gap-0.5 rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] p-0.5"
    >
      {RANGE_IDS.map((id) => {
        const active = id === range;
        return (
          // biome-ignore lint/a11y/useSemanticElements: segmented control intencional con el patrón ARIA radiogroup/radio (pills estilizadas, no inputs nativos)
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setRange(id)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-1 text-caption tabular-nums transition-colors duration-[var(--duration-fast)] ease-[var(--ease-out-soft)]",
              active
                ? "bg-[var(--color-bg)] text-[var(--color-ink)] shadow-soft"
                : "text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]",
            )}
          >
            {active ? (
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: "var(--color-blue-flat)" }}
              />
            ) : null}
            {RANGE_LABEL[id]}
          </button>
        );
      })}
    </div>
  );
}
