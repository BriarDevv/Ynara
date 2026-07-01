"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { d14 } from "@/content/deck";

/** Promoción · Redes (2/2). Las otras dos publicaciones, grandes. Mundo oscuro. */
export function SlideRedes2({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={d14.eyebrow} images={d14.b} />
    </Slide>
  );
}
