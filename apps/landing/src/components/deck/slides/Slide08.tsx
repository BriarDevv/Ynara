"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { useSlideActive } from "@/components/deck/deck-context";
import { DeckLivingField } from "@/components/deck/living-field/DeckLivingField";
import { Slide } from "@/components/deck/Slide";
import { d08 } from "@/content/deck";
import "./Slide08.css";

/**
 * L08 · Funcionalidades — los 3 pilares. Mundo marfil. Productividad / Memoria /
 * Bienestar como cards (mecánica de HorizontalModes traída a una grilla quieta).
 * Cierra con la intersección: "Y de cruzar las tres, aconseja".
 */
export function Slide08({ index }: { index: number }) {
  const active = useSlideActive(index);
  return (
    <Slide index={index} contentClassName="s08" backdrop={<DeckLivingField active={active} />}>
      <DeckEyebrow>{d08.eyebrow}</DeckEyebrow>
      <h2 className="deck-h2 s08__intro" data-reveal>
        {d08.intro}
      </h2>

      <div className="s08__grid">
        {d08.pillars.map((p, i) => (
          <article className="s08__card" data-reveal key={p.title}>
            <span className="s08__num">{`0${i + 1}`}</span>
            <h3 className="s08__card-title">{p.title}</h3>
            <p className="s08__card-note">{p.note}</p>
            <ul className="deck-list s08__feats">
              {p.features.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      <p className="s08__intersection" data-reveal>
        <span className="s08__diamond" aria-hidden />
        {d08.intersection}
      </p>
    </Slide>
  );
}
