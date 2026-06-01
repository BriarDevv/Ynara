"use client";

import { type CSSProperties, useMemo } from "react";
import type { ModeId } from "@/components/ui/modes";
import { SuggestionCard } from "@/components/ui/SuggestionCard";
import { pickRecommendations } from "../data/recommendations";

type Props = {
  interestedModes: readonly ModeId[];
  /** Al elegir una card: cambia el modo activo + prefillea el input. */
  onPick: (modeId: ModeId, prompt: string) => void;
};

/**
 * Grilla "Para arrancar" (plan §5.3): hasta 4 SuggestionCards filtradas y
 * priorizadas por los modos de interés del usuario.
 */
export function RecommendationsGrid({ interestedModes, onPick }: Props) {
  const recs = useMemo(() => pickRecommendations(interestedModes), [interestedModes]);

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-caption text-[var(--color-ink-muted)]">Para arrancar</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {recs.map((rec, i) => (
          // Stagger de entrada (§8.2): fade-up con delay por índice vía
          // --stagger-index; reduced-motion lo neutraliza global (patrón F2.1).
          <div
            key={rec.id}
            className="anim-stagger-up"
            style={{ "--stagger-index": Math.min(i, 5) } as CSSProperties}
          >
            <SuggestionCard
              modeId={rec.modeId}
              title={rec.title}
              subtitle={rec.subtitle}
              onClick={() => onPick(rec.modeId, rec.prefillPrompt)}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
