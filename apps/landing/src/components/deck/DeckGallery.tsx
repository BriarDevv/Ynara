"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import "./DeckGallery.css";

export type GalleryImage = { img: string; label?: string; alt: string };

/**
 * Galería de imágenes del deck: una fila de 1..N imágenes GRANDES que llenan el
 * centro de la lámina, con un rótulo chico bajo cada una. NINGÚN título las tapa —
 * el eyebrow (sección) va arriba y un caption opcional al pie. Pensada para las
 * láminas de evento/lanzamiento donde la imagen manda y la palabra sólo rotula
 * "qué es". Mundo oscuro. Si una imagen no trae `img`, muestra un placeholder.
 */
export function DeckGallery({
  eyebrow,
  images,
  caption,
}: {
  eyebrow?: string;
  images: ReadonlyArray<GalleryImage>;
  caption?: string;
}) {
  return (
    <>
      {eyebrow ? <DeckEyebrow>{eyebrow}</DeckEyebrow> : null}

      <ul className="deck-gallery__grid" data-count={images.length}>
        {images.map((it) => (
          <li className="deck-gallery__item" data-reveal key={it.img || it.alt}>
            <figure className="deck-gallery__figure">
              <span className="deck-gallery__frame">
                {it.img ? (
                  <img
                    className="deck-gallery__img"
                    src={it.img}
                    alt={it.alt}
                    loading="lazy"
                    decoding="async"
                  />
                ) : (
                  <span className="deck-gallery__placeholder" aria-hidden>
                    <span className="deck-gallery__placeholder-mark" />
                    <span className="deck-gallery__placeholder-text">Imagen</span>
                  </span>
                )}
              </span>
              {it.label ? (
                <figcaption className="deck-gallery__label">{it.label}</figcaption>
              ) : null}
            </figure>
          </li>
        ))}
      </ul>

      {caption ? (
        <p className="deck-gallery__caption" data-reveal>
          {caption}
        </p>
      ) : null}
    </>
  );
}
