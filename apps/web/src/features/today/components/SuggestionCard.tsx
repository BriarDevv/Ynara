import type { CSSProperties } from "react";
import { MODE_BY_ID } from "@/components/ui/modes";
import type { Suggestion } from "../api";

type Props = {
  suggestion: Suggestion;
  /** Índice en la lista, para el stagger de entrada (§8.2). */
  index: number;
};

/**
 * Una sugerencia de "Ynara sugiere" (wireframe 06/07): un acento tintado por el
 * modo + el título + su **porqué** (lo que la hace honesta, no una orden). Es
 * display-only en la Fase E; convertirla en acción (arrancar un chat con
 * prefill) es parte de la integración Hoy→Chat (Fase D / W5).
 */
export function SuggestionCard({ suggestion, index }: Props) {
  // El acento toma el tint plano del modo; transversal (mode null) → neutro.
  const accentColor = suggestion.mode
    ? MODE_BY_ID[suggestion.mode].tintVar
    : "var(--color-border-strong)";
  return (
    <li
      // Mismo lenguaje papel-sobre-canvas que PriorityRow: bg blanco + border
      // sutil. Antes era bg-soft, lo que generaba dos tonos de gris encimados
      // sin razón. El acento de modo queda como hairline a la izquierda.
      className="anim-stagger-up flex items-stretch gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-4"
      style={{ "--stagger-index": Math.min(index, 5) } as CSSProperties}
    >
      <span
        aria-hidden
        className="w-1 shrink-0 rounded-full"
        style={{ backgroundColor: accentColor }}
      />
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="text-body font-medium text-[var(--color-ink-deep)]">
          {suggestion.title}
        </span>
        <span className="text-body-sm text-[var(--color-ink-soft)]">{suggestion.why}</span>
      </span>
    </li>
  );
}
