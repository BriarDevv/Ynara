"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dRedes, dRedesAtencion } from "@/content/deck";

/** Promoción · Redes — post «Atención fragmentada» (2/5). Mundo oscuro. */
export function SlideRedesAtencion({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dRedes.eyebrow} images={[dRedesAtencion]} />
    </Slide>
  );
}
