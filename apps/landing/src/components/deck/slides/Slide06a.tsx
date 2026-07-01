"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { useSlideActive } from "@/components/deck/deck-context";
import { DeckLivingField } from "@/components/deck/living-field/DeckLivingField";
import { Slide } from "@/components/deck/Slide";
import { emphasizeYnara } from "@/components/deck/ynara-emphasis";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { d06a } from "@/content/deck";
import "./Slide06a.css";

/**
 * L06a · Desarrollo de la marca — NOMBRE E ISOTIPO. Mundo oscuro, registro NODOS.
 * Fondo: el CAMPO VIVO de la app (el mismo del home), montado como backdrop. El
 * lockup heroico (isotipo gradiente + wordmark, proporción canónica), la etimología
 * y el significado (figura / diamante). Entra en cascada.
 */
export function Slide06a({ index }: { index: number }) {
  const active = useSlideActive(index);
  return (
    <Slide index={index} contentClassName="s06a" backdrop={<DeckLivingField active={active} />}>
      <DeckEyebrow>{d06a.eyebrow}</DeckEyebrow>

      <div className="s06a__lockup" data-reveal>
        <YnaraMark className="s06a__mark" size={120} variant="gradient" />
        <span className="s06a__wordmark">{d06a.wordmark}</span>
      </div>

      <p className="deck-lead s06a__etymology" data-reveal>
        {d06a.etymology}
      </p>

      <dl className="s06a__defs" data-reveal>
        {d06a.notes.map((item) => (
          <div className="s06a__def" key={item.k}>
            <dt className="s06a__key">{item.k}</dt>
            <dd className="s06a__val">{emphasizeYnara(item.v)}</dd>
          </div>
        ))}
      </dl>
    </Slide>
  );
}
