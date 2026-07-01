"use client";

import { DeckGallery } from "@/components/deck/DeckGallery";
import { Slide } from "@/components/deck/Slide";
import { dLanzEquipo } from "@/content/deck";

/**
 * Lanzamiento · el equipo acreditado — las tres credenciales del equipo fundador,
 * grandes y claras (una por persona). Mundo oscuro.
 */
export function SlideLanzEquipo({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="deck-gallery">
      <DeckGallery eyebrow={dLanzEquipo.eyebrow} images={dLanzEquipo.pieces} />
    </Slide>
  );
}
