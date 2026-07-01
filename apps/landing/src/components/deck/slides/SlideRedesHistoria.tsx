"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dRedesHistoria } from "@/content/deck";

/**
 * Promoción · Redes — historia (5/5). Formato vertical (9:16), marco propio
 * vía `aspect` para que no quede un rectángulo panorámico con la imagen
 * perdida en el medio. Mundo oscuro.
 */
export function SlideRedesHistoria({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery
        eyebrow={dRedesHistoria.eyebrow}
        images={[dRedesHistoria]}
        caption={dRedesHistoria.caption}
      />
    </Slide>
  );
}
