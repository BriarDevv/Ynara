"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dRedes, dRedesTweet } from "@/content/deck";

/** Promoción · Redes — post formato tweet, «Desesperación» #mePaso (4/5). Mundo oscuro. */
export function SlideRedesTweet({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dRedes.eyebrow} images={[dRedesTweet]} />
    </Slide>
  );
}
