"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { Slide } from "@/components/deck/Slide";
import { d17 } from "@/content/deck";
import "./Slide17.css";

/**
 * L17 · Próximas funcionalidades — LISTA SIMPLE DE PROMESAS (mock editable). Mundo
 * oscuro, registro CALMA. "Subirte ahora es entrar antes que nadie." Cada promesa
 * es una tarjeta { título + descripción } con un marcador "+", lista para que el
 * equipo sume las suyas (editan `d17.promises` en deck.ts). Entran en cascada.
 */
export function Slide17({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="s17">
      <div className="s17__head">
        <DeckEyebrow>{d17.eyebrow}</DeckEyebrow>
        <h2 className="deck-title s17__statement" data-reveal>
          {d17.statement}
        </h2>
      </div>

      <ul className="s17__list">
        {d17.promises.map((p) => (
          <li className="s17__promise" data-reveal key={p.title}>
            <span className="s17__plus" aria-hidden />
            <h3 className="s17__promise-title">{p.title}</h3>
            <p className="s17__promise-body">{p.body}</p>
          </li>
        ))}
      </ul>
    </Slide>
  );
}
