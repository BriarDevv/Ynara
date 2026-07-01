"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { useSlideActive } from "@/components/deck/deck-context";
import { DeckLivingField } from "@/components/deck/living-field/DeckLivingField";
import { Slide } from "@/components/deck/Slide";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { d09 } from "@/content/deck";
import "./Slide09.css";

/**
 * L09 · Funcionalidades — la app. Mundo marfil, registro CALMA. Un PANEL de chat
 * (mockup del producto, mismo espíritu que VoiceChapter): header con la presencia
 * de Ynara "en línea" y un hilo donde, por cada modo, entran en cascada la
 * etiqueta, la burbuja del usuario y la respuesta de Ynara. La conversación se
 * arma sola → "le hablás como a una persona y resuelve".
 */

// Acento por modo (tokens de marca): azul calma / violeta señal.
const MODE_ACC: Record<string, string> = {
  Productividad: "var(--c-blue)",
  Memoria: "var(--c-violet)",
  Bienestar: "var(--c-blue-violet)",
  Aconseja: "var(--c-indigo)",
};

export function Slide09({ index }: { index: number }) {
  const active = useSlideActive(index);
  return (
    <Slide index={index} contentClassName="s09" backdrop={<DeckLivingField active={active} />}>
      <div className="s09__head">
        <DeckEyebrow>{d09.eyebrow}</DeckEyebrow>
        <h2 className="deck-h2 s09__statement" data-reveal>
          {d09.statement}
        </h2>
      </div>

      <div className="s09__panel">
        <div className="s09__bar" data-reveal>
          <span className="s09__avatar" aria-hidden>
            <YnaraMark size={20} variant="blue" />
          </span>
          <span className="s09__name">Ynara</span>
          <span className="s09__status">en línea</span>
        </div>

        <div className="s09__thread">
          {d09.chats.map((c) => (
            <div
              className="s09__ex"
              key={c.mode}
              style={{ "--mode-acc": MODE_ACC[c.mode] ?? "var(--c-blue)" } as React.CSSProperties}
            >
              <span className="s09__mode" data-reveal>
                {c.mode}
              </span>
              <p className="s09__bubble s09__user" data-reveal>
                {c.user}
              </p>
              <p className="s09__bubble s09__ynara" data-reveal>
                {c.ynara}
              </p>
            </div>
          ))}
        </div>
      </div>

      <p className="deck-meta s09__ph" data-reveal>
        ▸ {d09.placeholder}
      </p>
    </Slide>
  );
}
