"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dLanzStand } from "@/content/deck";

/**
 * Lanzamiento · el stand — una sola imagen grande del stand de Ynara en Nerdearla.
 * Mundo oscuro. La imagen manda; el caption sólo dice qué es.
 */
export function SlideLanzStand({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery
        eyebrow={dLanzStand.eyebrow}
        images={dLanzStand.pieces}
        caption={dLanzStand.caption}
      />
    </Slide>
  );
}
