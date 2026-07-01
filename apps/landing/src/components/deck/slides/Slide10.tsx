"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { useSlideActive } from "@/components/deck/deck-context";
import { DeckLivingField } from "@/components/deck/living-field/DeckLivingField";
import { Slide } from "@/components/deck/Slide";
import { d10 } from "@/content/deck";
import "./Slide10.css";

/**
 * L10 · Monetización — planes. Mundo marfil, registro calma (azul). Precio
 * EDITORIAL en franjas (regla horizontal + nombre + precio grande + features),
 * no cards en caja. Gratuito $0 · Premium (featured) con leve realce azul.
 */
export function Slide10({ index }: { index: number }) {
  const active = useSlideActive(index);
  return (
    <Slide index={index} contentClassName="s10" backdrop={<DeckLivingField active={active} />}>
      <DeckEyebrow>{d10.eyebrow}</DeckEyebrow>
      <h2 className="deck-h2 s10__title" data-reveal>
        {d10.title}
      </h2>

      <div className="s10__plans">
        {d10.plans.map((plan) => (
          <article
            className={`s10__plan${plan.featured ? " is-featured" : ""}`}
            data-reveal
            key={plan.name}
          >
            <div className="s10__head">
              <h3 className="s10__name">{plan.name}</h3>
              {plan.featured ? <span className="s10__tag">Recomendado</span> : null}
            </div>

            <div className="s10__price-row">
              <span className="s10__price">{plan.price}</span>
              <span className="s10__period">{plan.period}</span>
            </div>
            {"priceAlt" in plan && plan.priceAlt ? (
              <p className="s10__price-alt">{plan.priceAlt}</p>
            ) : null}

            <ul className="deck-list s10__feats">
              {plan.features.map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      <p className="deck-meta s10__note" data-reveal>
        {d10.note}
      </p>
    </Slide>
  );
}
