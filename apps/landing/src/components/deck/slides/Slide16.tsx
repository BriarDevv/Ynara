"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { d16 } from "@/content/deck";

/**
 * Promoción · Objetos (1/3). Tres renders de producto, GRANDES y rotulados, que
 * llenan la lámina. El caption sella "la marca que se toca"; el resto de los
 * objetos sigue en las dos láminas siguientes. Mundo oscuro.
 */
export function Slide16({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={d16.eyebrow} images={d16.a} caption={d16.caption} />
    </Slide>
  );
}
