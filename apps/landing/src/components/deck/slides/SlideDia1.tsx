"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { Slide } from "@/components/deck/Slide";
import { dDia1 } from "@/content/deck";
import "./SlideDia.css";

/**
 * Storytelling · Un día (imagen 1). Mundo oscuro, registro caos. La imagen la
 * pega el equipo (dDia1.img en src/content/deck.ts); mientras esté vacía se
 * muestra un placeholder, así la lámina ya queda armada.
 */
export function SlideDia1({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="sd">
      <DeckEyebrow>{dDia1.eyebrow}</DeckEyebrow>
      <figure className="sd__figure" data-reveal>
        {dDia1.img ? (
          <img className="sd__img" src={dDia1.img} alt={dDia1.alt} loading="lazy" decoding="async" />
        ) : (
          <span className="sd__placeholder" aria-hidden>
            <span className="sd__placeholder-mark" />
            <span className="sd__placeholder-text">Fotografía</span>
          </span>
        )}
      </figure>
      <p className="sd__caption" data-reveal>
        {dDia1.caption}
      </p>
    </Slide>
  );
}
