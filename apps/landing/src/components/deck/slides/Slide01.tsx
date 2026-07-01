"use client";

import { Slide } from "@/components/deck/Slide";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { d01 } from "@/content/deck";
import "./Slide01.css";

/**
 * L01 · Presentarnos — portada. Mundo oscuro. Lockup isotipo marfil + wordmark
 * colosal "Ynara", la tagline arriba y SÓLO los nombres del equipo al pie (sin
 * rótulo institucional: la portada es marca + autores, nada más).
 */
export function Slide01({ index }: { index: number }) {
  return (
    <Slide index={index} contentClassName="s01">
      {/* Bloque dominante: promesa + lockup viven juntos, centrados en el eje
          óptico. Sin banda muerta: el lockup pisa la tagline como un solo gesto. */}
      <div className="s01__hero">
        <p className="s01__tagline" data-reveal>
          {d01.tagline}
        </p>

        <div className="s01__lockup" data-reveal>
          <YnaraMark className="s01__mark" size={130} variant="ivory" />
          <span className="s01__wordmark">{d01.wordmark}</span>
        </div>
      </div>

      <div className="s01__foot">
        <p className="s01__authors" data-reveal>
          {d01.authors.join("  ·  ")}
        </p>
      </div>
    </Slide>
  );
}
