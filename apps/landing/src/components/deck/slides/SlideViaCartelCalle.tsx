"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dViaCartelCalle, dViaPublica } from "@/content/deck";

/** Promoción · Vía pública — cartel de calle (1/3, arranca el caption). Mundo oscuro. */
export function SlideViaCartelCalle({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery
        eyebrow={dViaPublica.eyebrow}
        images={[dViaCartelCalle]}
        caption={dViaCartelCalle.caption}
      />
    </Slide>
  );
}
