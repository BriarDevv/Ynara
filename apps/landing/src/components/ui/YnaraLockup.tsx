import type { CSSProperties } from "react";
import { YnaraMark } from "./YnaraMark";

type Tone = "dark" | "light";

/**
 * Lockup de marca CANÓNICO de UI (isotipo + wordmark "Ynara"), con las proporciones
 * EXACTAS del logo de la landing (SiteNav). Fuente única de verdad: cualquier lugar
 * que muestre el logo chico (nav, chrome del deck, etc.) usa este componente, así
 * SIEMPRE tiene la misma base y no puede divergir.
 *
 * Proporciones (derivadas del nav: isotipo 21px / wordmark 16px):
 *   · isotipo = 1.3125× el cuerpo del wordmark
 *   · alineación a baseline · gap = 0.625em
 *   · wordmark Space Grotesk, 600, tracking-tight (-0.025em)
 *
 * `size` = cuerpo del wordmark en px (base landing = 16). `tone`:
 *   · dark  → mundo oscuro: isotipo marfil + texto marfil
 *   · light → mundo marfil: isotipo azul + texto navy
 *
 * NOTA: este es el logo de UI/chico. El lockup HEROICO (isotipo gradiente + wordmark
 * colosal de la portada / lámina de marca) es otro tratamiento, con su propia
 * proporción em — no se mezcla con éste.
 */
export function YnaraLockup({
  size = 16,
  tone = "dark",
  className,
  style,
}: {
  size?: number;
  tone?: Tone;
  className?: string;
  style?: CSSProperties;
}) {
  const onLight = tone === "light";
  return (
    <span
      className={className}
      style={{
        display: "inline-flex",
        alignItems: "baseline",
        gap: `${(size * 0.625).toFixed(2)}px`,
        lineHeight: 1,
        ...style,
      }}
    >
      <YnaraMark size={Math.round(size * 1.3125)} variant={onLight ? "blue" : "ivory"} />
      <span
        style={{
          fontFamily: 'var(--font-display), "Space Grotesk", system-ui, sans-serif',
          fontSize: `${size}px`,
          fontWeight: 600,
          letterSpacing: "-0.025em",
          color: onLight ? "var(--c-navy)" : "var(--c-text-bright)",
          transition: "color 0.2s ease",
        }}
      >
        Ynara
      </span>
    </span>
  );
}
