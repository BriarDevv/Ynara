"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { d14 } from "@/content/deck";

/**
 * Promoción · Redes (1/2). Dos publicaciones reales de Instagram, GRANDES, que
 * llenan la lámina. El caption rotula el gesto + el handle; el resto de las
 * publicaciones va en la lámina siguiente. Mundo oscuro.
 */
export function Slide14({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={d14.eyebrow} images={d14.a} caption={d14.caption} />
    </Slide>
  );
}
