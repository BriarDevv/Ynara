"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dViaAfichePerdida, dViaPublica } from "@/content/deck";

/** Promoción · Vía pública — afiche guerrilla «Perdida» (3/3). Mundo oscuro. */
export function SlideViaAfichePerdida({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dViaPublica.eyebrow} images={[dViaAfichePerdida]} />
    </Slide>
  );
}
