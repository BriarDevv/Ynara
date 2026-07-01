"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dLanzEscenario } from "@/content/deck";

/**
 * Lanzamiento · el escenario — la imagen real del escenario principal de Nerdearla,
 * GRANDE y al frente (antes era un fondo fantasma a opacidad 0.13 y sólo se veía el
 * título). Mundo oscuro. Caption con el formato de la charla.
 */
export function SlideLanzEscenario({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery
        eyebrow={dLanzEscenario.eyebrow}
        images={dLanzEscenario.pieces}
        caption={dLanzEscenario.caption}
      />
    </Slide>
  );
}
