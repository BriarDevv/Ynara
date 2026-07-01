"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dRedes, dRedesAnsiedad } from "@/content/deck";

/** Promoción · Redes — post «Ansiedad de pestaña» (1/5, arranca el caption). Mundo oscuro. */
export function SlideRedesAnsiedad({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dRedes.eyebrow} images={[dRedesAnsiedad]} caption={dRedes.caption} />
    </Slide>
  );
}
