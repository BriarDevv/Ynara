"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dLanzFolleteria } from "@/content/deck";

/**
 * Lanzamiento · folletería — el folleto y los flyers, lado a lado y grandes.
 * Cierra el recap del evento. Mundo oscuro.
 */
export function SlideLanzFolleteria({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dLanzFolleteria.eyebrow} images={dLanzFolleteria.pieces} />
    </Slide>
  );
}
