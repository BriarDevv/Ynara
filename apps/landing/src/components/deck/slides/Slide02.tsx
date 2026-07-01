"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { Slide } from "@/components/deck/Slide";
import { d02 } from "@/content/deck";
import "./Slide02.css";

/**
 * Presentarnos — qué es Ynara, explicado de un vistazo. Mundo oscuro, registro
 * calma. En vez de un titular abstracto, un DIAGRAMA: tres pilares (Productividad
 * · Memoria · Bienestar), cada uno con su título grande y una línea concreta de
 * lo que hace; debajo, las tres corrientes confluyen en la síntesis —"te
 * aconseja"— destacada en violeta (el acento de señal). Lee la forma nueva de
 * `d02` (eyebrow, lead, pillars, intersection). Entrada en cascada por bloque.
 */
// Resalta el remate ("te aconseja") por PESO, no por color: el violeta como
// texto sobre el campo brillante quedaba turbio. Se parte por la coma del copy
// (verbatim de d02.intersection); si no hay coma, va entero.
const sep = d02.intersection.indexOf(", ");
const introPart = sep > -1 ? d02.intersection.slice(0, sep + 1) : "";
const keyPart = sep > -1 ? d02.intersection.slice(sep + 2) : d02.intersection;

export function Slide02({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="s02">
      <header className="s02__head">
        <DeckEyebrow className="s02__rotulo">{d02.eyebrow}</DeckEyebrow>
        <p className="deck-lead s02__lead" data-reveal>
          {d02.lead}
        </p>
      </header>

      <div className="s02__diagram">
        <ol className="s02__pillars" aria-label="Los tres pilares de Ynara">
          {d02.pillars.map((pillar, i) => (
            <li className="s02__pillar" data-reveal key={pillar.title}>
              <span className="s02__pillar-num" aria-hidden>
                {`0${i + 1}`}
              </span>
              <h3 className="s02__pillar-title">{pillar.title}</h3>
              <p className="s02__pillar-line">{pillar.line}</p>
            </li>
          ))}
        </ol>

        {/* Las tres corrientes bajan desde el centro de cada pilar y se cruzan en
            la síntesis, que cuelga del eje de la columna central de la grilla. */}
        <div className="s02__confluence" aria-hidden data-reveal>
          <svg
            className="s02__streams"
            viewBox="0 0 600 80"
            preserveAspectRatio="none"
            focusable="false"
            role="presentation"
            aria-hidden="true"
          >
            <path d="M100 0 C100 48 300 32 300 80" />
            <path d="M300 0 L300 80" />
            <path d="M500 0 C500 48 300 32 300 80" />
          </svg>
        </div>

        {/* Grilla espejo de los pilares: el pill se ancla a la columna central →
            queda sobre el eje del diagrama, no flotando al centro del bloque. */}
        <div className="s02__synthesis">
          <p className="s02__intersection" data-reveal>
            <span className="s02__intersection-diamond" aria-hidden />
            <span className="s02__intersection-text">
              {introPart && (
                <span className="s02__intersection-intro">{introPart} </span>
              )}
              <span className="s02__intersection-key">{keyPart}</span>
            </span>
          </p>
        </div>
      </div>
    </Slide>
  );
}
