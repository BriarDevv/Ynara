"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dLanzPiezas } from "@/content/deck";

/**
 * Lanzamiento · piezas físicas — señalética · afiche en Konex · roll-up, las tres
 * lado a lado y GRANDES, sin título encima. Abren la oratoria de lanzamiento:
 * "estuvimos, físicamente, en Nerdearla". Mundo oscuro.
 */
export function SlideLanzPiezas({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dLanzPiezas.eyebrow} images={dLanzPiezas.pieces} />
    </Slide>
  );
}
