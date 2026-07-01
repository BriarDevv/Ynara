"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { d16 } from "@/content/deck";

/** Promoción · Objetos (3/3). Buzo + tote, grandes y rotulados. Mundo oscuro. */
export function SlideObjetos3({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={d16.eyebrow} images={d16.c} />
    </Slide>
  );
}
