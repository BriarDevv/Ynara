"use client";

import { DeckEyebrow } from "@/components/deck/DeckEyebrow";
import { useSlideActive } from "@/components/deck/deck-context";
import { DeckLivingField } from "@/components/deck/living-field/DeckLivingField";
import { Slide } from "@/components/deck/Slide";
import { d06b } from "@/content/deck";
import "./Slide06b.css";

/**
 * L06b · Desarrollo de la marca — TIPOGRAFÍA Y COLOR. Mundo oscuro, registro NODOS.
 * Fondo: el CAMPO VIVO de la app. El sistema visual se MUESTRA en dos bloques sobre
 * superficies de vidrio (para que las muestras se lean CLARAS sobre el campo): la
 * paleta (chips + HEX) y las tipografías (muestra real de cada familia).
 */
export function Slide06b({ index }: { index: number }) {
  const active = useSlideActive(index);
  return (
    <Slide index={index} contentClassName="s06b" backdrop={<DeckLivingField active={active} />}>
      <DeckEyebrow>{d06b.eyebrow}</DeckEyebrow>

      <div className="s06b__grid">
        {/* Colores: muestras de la paleta de marca. */}
        <div className="s06b__block" data-reveal>
          <span className="s06b__block-label">Color</span>
          <ul className="s06b__swatches">
            {d06b.palette.map((c) => (
              <li className="s06b__swatch" key={c.name}>
                <span className="s06b__chip" style={{ background: c.token }} aria-hidden />
                <span className="s06b__chip-name">{c.name}</span>
                <span className="s06b__chip-hex">{c.hex}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Tipografías: muestra real de cada familia. */}
        <div className="s06b__block" data-reveal>
          <span className="s06b__block-label">Tipografía</span>
          <ul className="s06b__fonts">
            {d06b.typefaces.map((t) => (
              <li className="s06b__font" key={t.name}>
                <span className="s06b__font-sample" style={{ fontFamily: t.varName }}>
                  Aa
                </span>
                <span className="s06b__font-meta">
                  <span className="s06b__font-name" style={{ fontFamily: t.varName }}>
                    {t.name}
                  </span>
                  <span className="s06b__font-role">{t.role}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Slide>
  );
}
