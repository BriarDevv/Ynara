"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { Slide } from "@/components/deck/Slide";
import { d04 } from "@/content/deck";
import "./Slide04.css";

/**
 * El problema — el caos con humor (8 → 1). Mundo oscuro, registro CAOS (violeta).
 * Lectura en TRES TIEMPOS: el problema enunciado arriba ("Vivís entre ocho apps."),
 * el COLAPSO 8→1 abajo (ocho chips dispersos · flecha · "Ynara es una.") y los tres
 * beats irónicos al pie. La flecha vuelve explícito que las ocho se vuelven una —
 * antes los chips rotados leían como glitch y la relación con la respuesta no cerraba.
 */
// El último beat firma el cierre irónico ("El pegamento sos vos."): se distingue
// del par anterior con peso y acento de señal sobre "vos" — sin tocar el copy.
const LAST_BEAT = d04.beats.length - 1;

export function Slide04({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="s04">
      <header className="s04__head">
        <DeckEyebrow className="s04__rotulo">{d04.eyebrow}</DeckEyebrow>
        <p className="deck-h2 s04__problem" data-reveal>
          {d04.problemLine}
        </p>
      </header>

      <ul className="s04__chips" aria-label="Las ocho apps dispersas">
        {d04.apps.map((app) => (
          <li className="s04__chip" data-reveal key={app}>
            {app}
          </li>
        ))}
      </ul>

      {/* El puente 8→1: una flecha que hace explícito el colapso. Marfil (legible)
          con halo violeta de señal — el violeta como texto fino no contrastaba. */}
      <div className="s04__bridge" aria-hidden data-reveal>
        <svg
          className="s04__arrow"
          viewBox="0 0 56 24"
          fill="none"
          focusable="false"
          role="presentation"
          aria-hidden="true"
        >
          <path
            d="M3 12 H50 M50 12 L40 4 M50 12 L40 20"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      <div className="s04__answer">
        <p className="deck-title s04__one" data-reveal>
          {d04.answerLine}
        </p>
      </div>

      <ul className="s04__beats" aria-label="Apuntes del caos cotidiano">
        {d04.beats.map((beat, i) => {
          const isClosing = i === LAST_BEAT;
          // Cierre: acentúa la última palabra ("vos.") sin reescribir el copy.
          const cut = beat.lastIndexOf(" ");
          return (
            <li
              className={`deck-meta s04__beat${isClosing ? " s04__beat--closing" : ""}`}
              data-reveal
              key={beat}
            >
              {isClosing && cut > -1 ? (
                <>
                  {beat.slice(0, cut + 1)}
                  <span className="s04__beat-accent">{beat.slice(cut + 1)}</span>
                </>
              ) : (
                beat
              )}
            </li>
          );
        })}
      </ul>
    </Slide>
  );
}
