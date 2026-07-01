"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import "./DeckGallery.css";

export type GalleryImage = {
  img: string;
  label?: string;
  alt: string;
  /**
   * "cover" (default) = llena el marco, recorta lo que sobre — para fotos
   * reales pensadas para sangrar. "contain" = la imagen ENTERA siempre
   * visible, sin recortar — usalo para piezas con texto/UI que no puede
   * perder borde (posts, historias, capturas de pantalla, OOH con QR).
   */
  fit?: "cover" | "contain";
  /**
   * Proporción real de la imagen (ej. "4/5", "3/2", "9/16"). Con `fit:
   * "contain"`, el MARCO adopta esta proporción (en vez de estirarse al
   * alto/ancho completo de la celda) para que no queden franjas de letterbox
   * — la imagen ocupa el marco casi entero, centrada en la lámina.
   */
  aspect?: string;
};

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
  className,
}: {
  eyebrow?: string;
  images: ReadonlyArray<GalleryImage>;
  caption?: string;
  /** Clase extra para el grid — p.ej. angostar una galería de 1 imagen vertical. */
  className?: string;
}) {
  return (
    <>
      {eyebrow ? <DeckEyebrow>{eyebrow}</DeckEyebrow> : null}

      <ul
        className={className ? `deck-gallery__grid ${className}` : "deck-gallery__grid"}
        data-count={images.length}
      >
        {images.map((it) => (
          <li className="deck-gallery__item" data-reveal key={it.img || it.alt}>
            <figure className="deck-gallery__figure">
              <span
                className={
                  it.aspect ? "deck-gallery__frame deck-gallery__frame--fit" : "deck-gallery__frame"
                }
                style={it.aspect ? { aspectRatio: it.aspect } : undefined}
              >
                {it.img ? (
                  <img
                    className="deck-gallery__img"
                    src={it.img}
                    alt={it.alt}
                    loading="lazy"
                    decoding="async"
                    style={it.fit ? { objectFit: it.fit } : undefined}
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
