"use client";

import { Slide } from "@/components/deck/Slide";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { dGracias } from "@/content/deck";
import "./SlideGracias.css";

/**
 * L19 · Gracias — cierre humano y bookend de la portada. Mundo oscuro. El logo de
 * la marca GRANDE (lockup colosal: isotipo marfil + wordmark, misma proporción
 * canónica que la L01), "Gracias" como remate arriba y los nombres del equipo al
 * pie. El deck abre y cierra sobre el mismo lockup.
 */
export function SlideGracias({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="sgr">
      <div className="sgr__hero">
        <p className="sgr__word" data-reveal>
          {dGracias.word}
        </p>

        <div className="sgr__lockup" data-reveal>
          <YnaraMark className="sgr__mark" size={130} variant="ivory" />
          <span className="sgr__wordmark">{dGracias.wordmark}</span>
        </div>
      </div>

      <div className="sgr__foot">
        <p className="sgr__authors" data-reveal>
          {dGracias.authors.join("  ·  ")}
        </p>
      </div>
    </Slide>
  );
}
