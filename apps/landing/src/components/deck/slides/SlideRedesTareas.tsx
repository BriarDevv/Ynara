"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dRedes, dRedesTareas } from "@/content/deck";

/** Promoción · Redes — post de la lista de tareas surreal (3/5). Mundo oscuro. */
export function SlideRedesTareas({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dRedes.eyebrow} images={[dRedesTareas]} />
    </Slide>
  );
}
