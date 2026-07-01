"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { NodeField } from "@/components/deck/NodeField";
import { Slide } from "@/components/deck/Slide";
import { d18 } from "@/content/deck";
import "./Slide18.css";

/**
 * L18 · Cierre — el finale. Mundo oscuro, registro CALMA (azul). Es el clímax:
 * la síntesis a gran escala (deck-title) cierra el arco humor↔memoria, el
 * signoff sella la voz y el CTA remata la venta. El campo de nodos respira
 * detrás como la corriente ya en orden. Todo entra en cascada; el CTA, último.
 *
 * El CTA es un <a> con clase `.deck-cta`: el guard de click del Deck no
 * intercepta anclas, así que navega sin disparar el avance de lámina.
 */
export function Slide18({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="s18">
      <NodeField className="s18__field" />

      <div className="s18__content">
        <DeckEyebrow>{d18.eyebrow}</DeckEyebrow>

        <h1 className="deck-title s18__synthesis" data-reveal>
          {d18.synthesis}
        </h1>

        <p className="deck-lead s18__signoff" data-reveal>
          {d18.signoff}
        </p>

        <a className="deck-cta s18__cta" href={d18.cta.href} data-reveal>
          {d18.cta.label}
        </a>
      </div>
    </Slide>
  );
}
