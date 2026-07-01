"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { Slide } from "@/components/deck/Slide";
import { emphasizeYnara } from "@/components/deck/ynara-emphasis";
import { d05 } from "@/content/deck";
import "./Slide05.css";

/**
 * L05 · La identidad — "Calma en el caos." Mundo oscuro, registro NODES.
 *
 * Estructura: TÍTULO arriba · DÍPTICO de dos FOTOS grande, que llena el CENTRO
 * (el caos del día enredado → la calma con Ynara, con la flecha del lenguaje de
 * marca entre ambas) · PIE (support) abajo. El visual manda; la palabra encuadra.
 *
 * Las fotos las pega el equipo (d05.chaos.img / d05.calm.img en deck.ts); mientras
 * estén vacías, cada panel muestra un placeholder rotulado. [data-reveal] + { index }.
 */
export function Slide05({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="s05">
      <header className="s05__head">
        <DeckEyebrow>{d05.eyebrow}</DeckEyebrow>
        <h2 className="deck-title s05__statement" data-reveal>
          {d05.statement}
        </h2>
      </header>

      {/* El visual, protagonista: díptico grande de dos estados (dos fotos). */}
      <figure className="s05__diptych" data-reveal>
        {/* Estado 1 · caos */}
        <div className="s05__panel s05__panel--chaos">
          {d05.chaos.img ? (
            <img
              className="s05__img"
              src={d05.chaos.img}
              alt={d05.chaos.alt}
              loading="lazy"
              decoding="async"
            />
          ) : (
            <span className="s05__placeholder" aria-hidden>
              <span className="s05__placeholder-mark" />
              <span className="s05__placeholder-text">Fotografía</span>
            </span>
          )}
          <span className="s05__tag s05__tag--chaos">{d05.chaos.tag}</span>
        </div>

        {/* Flecha de transición: el movimiento caos→calma. */}
        <div className="s05__bridge" aria-hidden>
          <svg
            viewBox="0 0 64 24"
            fill="none"
            preserveAspectRatio="xMidYMid meet"
            aria-hidden
            role="presentation"
          >
            <path className="s05__arrow-line" d="M4 12 H52" />
            <path className="s05__arrow-head" d="M44 5 L56 12 L44 19" />
          </svg>
        </div>

        {/* Estado 2 · calma */}
        <div className="s05__panel s05__panel--calm">
          {d05.calm.img ? (
            <img
              className="s05__img"
              src={d05.calm.img}
              alt={d05.calm.alt}
              loading="lazy"
              decoding="async"
            />
          ) : (
            <span className="s05__placeholder" aria-hidden>
              <span className="s05__placeholder-mark" />
              <span className="s05__placeholder-text">Fotografía</span>
            </span>
          )}
          <span className="s05__tag s05__tag--calm">{d05.calm.tag}</span>
        </div>
      </figure>

      <p className="deck-lead s05__support" data-reveal>
        {emphasizeYnara(d05.support)}
      </p>
    </Slide>
  );
}
