import type { ReactNode } from "react";

/**
 * Resalta CADA mención textual de "Ynara" en negrita, de forma consistente en
 * todo el deck. No toca el wordmark del logo (isotipo + marca, que se renderiza
 * aparte): esto es sólo para la palabra cuando aparece dentro de un PÁRRAFO.
 * Parte el texto por la palabra y envuelve cada ocurrencia en
 * `<strong class="deck-ynara">`.
 */
export function emphasizeYnara(text: string): ReactNode {
  return text.split(/(Ynara)/g).map((chunk, i) =>
    chunk === "Ynara" ? (
      <strong className="deck-ynara" key={`yn-${i}`}>
        Ynara
      </strong>
    ) : (
      chunk
    ),
  );
}
