"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { Slide } from "@/components/deck/Slide";
import { d07 } from "@/content/deck";
import "./Slide07.css";

/**
 * L07 · Landing — la página. Mundo oscuro, registro CALMA (azul). Dos columnas:
 * a la izquierda el statement "De curioso a usuario fiel." + support y el
 * recorrido rotulado (inicio → precio → CTA); a la derecha una ventana de
 * browser (chrome con tres puntos) que enmarca la captura HEROÍNA (shots[0] =
 * inicio) completa —sin recortes— y, debajo, las otras dos capturas (precio y
 * cierre/CTA) como apoyo, también completas. Las imágenes son las protagonistas;
 * el texto sólo encuadra. Cascada de reveals; apila bajo ~860px.
 *
 * Nota de legibilidad: las capturas se muestran con `object-fit: contain` sobre
 * pantalla oscura, así ningún chip ni botón queda cortado (lo que antes "leía
 * como un bug"). El recorrido — inicio → precio → CTA — acompaña el mensaje
 * "de curioso a usuario fiel".
 */
export function Slide07({ index }: { index: number }) {
  const [hero, ...thumbs] = d07.shots;
  // Rótulos del recorrido derivados del alt (después del guión largo).
  const stepOf = (alt: string) => alt.split("—").pop()?.trim() ?? "";

  return (
    <Slide index={index} contentClassName="s07">
      <div className="s07__text">
        <DeckEyebrow>{d07.eyebrow}</DeckEyebrow>
        <h2 className="deck-title" data-reveal>
          {d07.statement}
        </h2>
        <p className="deck-lead" data-reveal>
          {d07.support}
        </p>
        <ol className="s07__journey" data-reveal aria-hidden>
          {d07.shots.map((shot, i) => (
            <li className="s07__step" key={shot.img}>
              <span className="s07__step-num">{i + 1}</span>
              <span className="s07__step-label">{stepOf(shot.alt)}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="s07__gallery">
        <figure className="s07__window" data-reveal>
          <div className="s07__chrome" aria-hidden>
            <span className="s07__dot" />
            <span className="s07__dot" />
            <span className="s07__dot" />
            <span className="s07__addr">ynara.app</span>
          </div>
          <div className="s07__screen">
            <img
              className="s07__shot"
              src={hero.img}
              alt={hero.alt}
              loading="lazy"
              decoding="async"
            />
          </div>
        </figure>

        <div className="s07__thumbs" data-reveal>
          {thumbs.map((shot) => (
            <figure className="s07__thumb" key={shot.img}>
              <div className="s07__thumb-screen">
                <img
                  className="s07__thumb-shot"
                  src={shot.img}
                  alt={shot.alt}
                  loading="lazy"
                  decoding="async"
                />
              </div>
              <figcaption className="s07__thumb-label">{stepOf(shot.alt)}</figcaption>
            </figure>
          ))}
        </div>
      </div>
    </Slide>
  );
}
