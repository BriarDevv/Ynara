"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { d16 } from "@/content/deck";

/** Promoción · Objetos (2/3). Lapicera + remera, grandes y rotuladas. Mundo oscuro. */
export function SlideObjetos2({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={d16.eyebrow} images={d16.b} />
    </Slide>
  );
}
