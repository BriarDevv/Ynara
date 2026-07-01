"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { Slide } from "@/components/deck/Slide";
import { dDia2 } from "@/content/deck";
import "./SlideDia.css";

/**
 * Storytelling · Un día (imagen 2). Mundo oscuro, registro caos. Gemela de
 * SlideDia1: la imagen la pega el equipo (dDia2.img); placeholder si está vacía.
 */
export function SlideDia2({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="sd">
      <DeckEyebrow>{dDia2.eyebrow}</DeckEyebrow>
      <figure className="sd__figure" data-reveal>
        {dDia2.img ? (
          <img className="sd__img" src={dDia2.img} alt={dDia2.alt} loading="lazy" decoding="async" />
        ) : (
          <span className="sd__placeholder" aria-hidden>
            <span className="sd__placeholder-mark" />
            <span className="sd__placeholder-text">Fotografía</span>
          </span>
        )}
      </figure>
      <p className="sd__caption" data-reveal>
        {dDia2.caption}
      </p>
    </Slide>
  );
}
