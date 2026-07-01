"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dViaParadaColectivo, dViaPublica } from "@/content/deck";

/** Promoción · Vía pública — parada de colectivo (2/3). Mundo oscuro. */
export function SlideViaParadaColectivo({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dViaPublica.eyebrow} images={[dViaParadaColectivo]} />
    </Slide>
  );
}
