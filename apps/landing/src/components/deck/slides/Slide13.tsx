"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { Slide } from "@/components/deck/Slide";
import { d13 } from "@/content/deck";
import "./Slide13.css";

/**
 * L13 · Lanzamiento — la demo (actuada). Mundo oscuro, registro CALMA.
 *
 * NO repite el hilo de chat de la app (slide claro): en vez del historial entero
 * en chico, acá la demo se ACTÚA en vivo y se muestra GRANDE. Dos intercambios
 * (d13.chats), cada uno como un acto: el pedido del usuario en grande y la
 * respuesta de Ynara aún más grande, con su modo como acento. La pantalla
 * respalda al orador mientras dispara la demo "en treinta segundos". El Plan B
 * va al pie, discreto.
 *
 * Legibilidad (estándar oscuro): texto de Ynara en marfil pleno; el pedido del
 * usuario en marfil con opacidad alta; etiquetas de modo en el acento. Nada por
 * debajo del umbral AA, nada de azul-grisáceo tenue.
 */
export function Slide13({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="s13">
      <header className="s13__head">
        <DeckEyebrow>{d13.eyebrow}</DeckEyebrow>
        <h2 className="deck-h2 s13__statement" data-reveal>
          {d13.statement}
        </h2>
        <span className="s13__live" data-reveal>
          <span className="s13__pulse" aria-hidden />
          en vivo
        </span>
      </header>

      <ol className="s13__acts">
        {d13.chats.map((c, i) => (
          <li className="s13__act" key={c.mode} data-reveal>
            <div className="s13__meta">
              <span className="s13__num">{String(i + 1).padStart(2, "0")}</span>
              <span className="s13__mode">{c.mode}</span>
            </div>
            <p className="s13__ask">
              <span className="s13__ask-tag" aria-hidden>
                Le decís
              </span>
              {c.user}
            </p>
            <p className="s13__reply">{c.ynara}</p>
          </li>
        ))}
      </ol>

      <p className="deck-meta s13__fallback" data-reveal>
        {d13.fallback}
      </p>
    </Slide>
  );
}
