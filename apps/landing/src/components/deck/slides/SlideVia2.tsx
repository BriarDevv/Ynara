"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { d15 } from "@/content/deck";

/** Promoción · Vía pública (2/2). Los otros dos renders de OOH, grandes. Mundo oscuro. */
export function SlideVia2({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={d15.eyebrow} images={d15.b} />
    </Slide>
  );
}
