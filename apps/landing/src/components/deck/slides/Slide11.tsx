"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { useSlideActive } from "@/components/deck/deck-context";
import { DeckLivingField } from "@/components/deck/living-field/DeckLivingField";
import { Slide } from "@/components/deck/Slide";
import { d11 } from "@/content/deck";
import "./Slide11.css";

/**
 * L11 · Monetización — viabilidad. Mundo marfil, registro calma. Evoca el LEDGER
 * numerado de Trust: números masivos ($0 / US$70 / ~15) con su regla fina y una
 * lectura corta por fila. La pantalla cierra el argumento: el negocio funciona.
 */
export function Slide11({ index }: { index: number }) {
  const active = useSlideActive(index);
  return (
    <Slide index={index} contentClassName="s11" backdrop={<DeckLivingField active={active} />}>
      <DeckEyebrow>{d11.eyebrow}</DeckEyebrow>
      <h2 className="deck-title s11__statement" data-reveal>
        {d11.statement}
      </h2>

      <dl className="s11__ledger">
        {d11.ledger.map((row) => (
          <div className="s11__row" data-reveal key={row.title}>
            <dt className="s11__num">{row.num}</dt>
            <dd className="s11__detail">
              <span className="s11__title">{row.title}</span>
              <span className="s11__body">{row.body}</span>
            </dd>
          </div>
        ))}
      </dl>
    </Slide>
  );
}
