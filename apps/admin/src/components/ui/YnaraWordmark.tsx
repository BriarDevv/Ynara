import { useId } from "react";
import { YnaraSymbol } from "./YnaraMark";

/**
 * Variante por fondo del lockup (DESIGN.md §11.1):
 * - `color`: símbolo a color + "Ynara" en Noche. Sobre claro/neutro.
 * - `mono-light`: símbolo + texto marfil. Sobre Noche o fondos de marca.
 * - `mono-dark`: símbolo + texto Noche. Mono sobre claro.
 */
export type YnaraWordmarkVariant = "color" | "mono-light" | "mono-dark";

/**
 * Color del texto por variante. El símbolo lo resuelve `YnaraSymbol`. Tonos
 * FIJOS, no tokens que sigan el tema (`--color-ink-*`): la variante se elige
 * por el fondo, no por el tema, así `color`/`mono-dark` siempre leen oscuro
 * sobre claro y `mono-light` siempre marfil sobre Noche.
 */
const TEXT_FILL: Record<YnaraWordmarkVariant, string> = {
  color: "var(--color-noche, #242c3f)",
  "mono-light": "var(--color-marfil, #f3f0ea)",
  "mono-dark": "var(--color-noche, #242c3f)",
};

const SYMBOL_VARIANT = {
  color: "color",
  "mono-light": "mono-light",
  "mono-dark": "mono-dark",
} as const;

type Props = {
  /** Altura del lockup en px. El ancho sale del viewBox. */
  height?: number;
  variant?: YnaraWordmarkVariant;
  className?: string;
};

/**
 * `YnaraWordmark` — el lockup oficial símbolo + "Ynara" (§11.1). Un solo SVG
 * con **baseline compartida**: el símbolo (geometría 800×700 de `YnaraSymbol`)
 * se escala y traslada para que **los pies de la "Y" caigan sobre la baseline
 * del texto** (y≈19.8 en el viewBox de 22 de alto), nunca alineado a mano con
 * `align-items:center`.
 *
 * El símbolo natural va de y=48 (punta del diamante) a y=590 (pies). La
 * transformación lo lleva a una altura visual ~18 con los pies en 19.8 y el
 * borde izquierdo en x≈0.6; el texto arranca después con aire de marca.
 *
 * Decorativo o de marca: el `<svg>` lleva `role="img"` + `aria-label="Ynara"`,
 * así el lockup se anuncia una sola vez (el símbolo interno no compite).
 */
export function YnaraWordmark({ height = 22, variant = "color", className }: Props) {
  const id = useId();
  // Mismas medidas que el lockup oficial del mockup (brand.jsx): símbolo en caja
  // 22×22 a (0,0), texto en x=28.6/baseline 19.8, viewBox 73.7×22.
  const VIEWBOX_W = 73.7;
  const VIEWBOX_H = 22;
  const width = height * (VIEWBOX_W / VIEWBOX_H);

  return (
    <svg
      viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
      width={width}
      height={height}
      role="img"
      aria-label="Ynara"
      className={className}
      // overflow visible: el ancho del texto depende de la fuente; si "Ynara"
      // excede el viewBox por unas décimas, igual se ve (no se recorta).
      style={{ overflow: "visible", display: "block" }}
    >
      {/* Símbolo oficial en caja 22×22 a (0,0) — equivalente al `<use
          width=22 height=22>` del mockup: scale 22/1012.54 = 0.021728. El
          artwork tiene su padding propio, así sus pies caen sobre la baseline
          del texto (y≈19.8) → símbolo y wordmark comparten la MISMA base. Va en
          un <g> (no <svg> anidado) para no duplicar el role=img del lockup. */}
      <g transform="scale(0.021728)">
        <YnaraSymbol variant={SYMBOL_VARIANT[variant]} idPrefix={id} />
      </g>
      <text
        x="28.6"
        y="19.8"
        fontSize="14.3"
        fontWeight="600"
        letterSpacing="-0.2"
        fill={TEXT_FILL[variant]}
        style={{ fontFamily: "var(--font-display), 'Space Grotesk', system-ui, sans-serif" }}
      >
        Ynara
      </text>
    </svg>
  );
}
