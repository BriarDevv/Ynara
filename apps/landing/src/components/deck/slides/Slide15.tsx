"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { d15 } from "@/content/deck";

/**
 * Promoción · Vía pública (1/2). Dos renders de OOH, GRANDES y rotulados, que
 * llenan la lámina. El caption resume el gesto; los otros dos van en la siguiente.
 * Mundo oscuro.
 */
export function Slide15({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={d15.eyebrow} images={d15.a} caption={d15.caption} />
    </Slide>
  );
}
