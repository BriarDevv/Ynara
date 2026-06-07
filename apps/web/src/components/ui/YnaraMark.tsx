import { useId } from "react";

/**
 * Variante por fondo del símbolo (DESIGN.md §11.1):
 * - `color`: la "Y" azul→celeste con relieve + diamante violeta. Sobre claro/neutro.
 * - `mono-dark` (`#242C3F`): silueta sólida sobre claro cuando se quiere mono.
 * - `mono-light` (`#F3F0EA`): silueta sobre Noche o fondos de marca (jamás el
 *   símbolo a color sobre Noche — pierde contraste, §11.1).
 * - `avatar`: cuadrado redondeado (app-icon) — símbolo mono-light sobre Noche.
 *   Solo como ícono de app, nunca inline en un lockup.
 */
export type YnaraMarkVariant = "color" | "mono-dark" | "mono-light" | "avatar";

// Geometría del símbolo (viewBox 800×700). Compartida entre YnaraMark y
// YnaraWordmark — única fuente de los paths, sin duplicar.
const PATH_Y_BASE =
  "M352 590 C352 590 352 470 352 427 C352 375 324 318 257 212 C241 188 218 173 192 181 C167 188 156 211 168 233 C221 335 269 413 302 485 C320 523 329 557 329 590 L471 590 C471 557 480 523 498 485 C531 413 579 335 632 233 C644 211 633 188 608 181 C582 173 559 188 543 212 C476 318 448 375 448 427 C448 470 448 590 448 590 Z";
const PATH_Y_RELIEF =
  "M403 590 C403 541 394 498 378 457 C348 385 312 320 255 227 C247 213 238 201 233 192 C252 186 269 194 281 213 C343 311 379 372 399 422 C419 372 455 311 517 213 C529 194 546 186 565 192 C560 201 551 213 543 227 C486 320 450 385 420 457 C404 498 395 541 395 590 Z";
const PATH_DIAMOND = "M400 48 L464 112 L400 176 L336 112 Z";

const MONO_FILL = {
  "mono-dark": "var(--color-noche, #242c3f)",
  "mono-light": "var(--color-marfil, #f3f0ea)",
} as const;

/**
 * Contenido del símbolo en coordenadas 800×700, sin el `<svg>` contenedor —
 * para que YnaraMark lo envuelva en su viewBox y YnaraWordmark lo anide en su
 * lockup. `idPrefix` (de `useId`) hace únicos los ids de los gradientes: sin
 * esto, dos logos en la misma página comparten `id` y el segundo hereda el
 * gradiente del primero.
 */
export function YnaraSymbol({
  variant,
  idPrefix,
}: {
  variant: Exclude<YnaraMarkVariant, "avatar">;
  idPrefix: string;
}) {
  if (variant === "mono-dark" || variant === "mono-light") {
    // Silueta plana: el relieve es un realce que en mono no aporta (cae dentro
    // de la base, mismo color), así que se omite — base + diamante alcanzan.
    const fill = MONO_FILL[variant];
    return (
      <>
        <path d={PATH_Y_BASE} fill={fill} />
        <path d={PATH_DIAMOND} fill={fill} />
      </>
    );
  }

  // Variante color: stops de la paleta oficial v4 (§3.4) — azul→celeste en la
  // "Y", celeste→lavanda en el relieve y violeta→violáceo en el diamante. Los
  // fallbacks hex cubren el caso en que `var()` no resuelva (Safari viejo con
  // SVG fuera del flujo CSS). Migrado de los stops legacy blue-base/relief/violet.
  const baseId = `${idPrefix}-base`;
  const reliefId = `${idPrefix}-relief`;
  const diamondId = `${idPrefix}-diamond`;
  return (
    <>
      <defs>
        <linearGradient
          id={baseId}
          x1="240"
          y1="590"
          x2="560"
          y2="160"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="var(--color-azul, #2f5aa6)" />
          <stop offset="1" stopColor="var(--color-celeste, #6e92cc)" />
        </linearGradient>
        <linearGradient
          id={reliefId}
          x1="330"
          y1="580"
          x2="470"
          y2="185"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="var(--color-celeste, #6e92cc)" stopOpacity="0.88" />
          <stop offset="1" stopColor="var(--color-lavanda, #8b9ad0)" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient
          id={diamondId}
          x1="400"
          y1="48"
          x2="400"
          y2="168"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="var(--color-violeta, #8165a3)" />
          <stop offset="1" stopColor="var(--color-violaceo, #5c6fb3)" />
        </linearGradient>
      </defs>
      <path d={PATH_Y_BASE} fill={`url(#${baseId})`} />
      <path d={PATH_Y_RELIEF} fill={`url(#${reliefId})`} />
      <path d={PATH_DIAMOND} fill={`url(#${diamondId})`} />
    </>
  );
}

type Props = {
  size?: number;
  variant?: YnaraMarkVariant;
  className?: string;
  title?: string;
};

/**
 * Símbolo de Ynara (la "Y" + diamante). Logo SVG con variante por fondo
 * (§11.1). Decorativo o semántico según `title`: con título lleva
 * `role="img"` + `aria-label`. Para el lockup símbolo+wordmark usar
 * `YnaraWordmark` (baseline compartida), nunca componer a mano.
 */
export function YnaraMark({ size = 96, variant = "color", className, title = "Ynara" }: Props) {
  const id = useId();

  if (variant === "avatar") {
    // App-icon: cuadrado redondeado Noche con la silueta marfil centrada. El
    // símbolo (contenido 800×700) se escala 0.85 y se centra en el box 800×800.
    return (
      <svg
        viewBox="0 0 800 800"
        width={size}
        height={size}
        role="img"
        aria-label={title}
        className={className}
      >
        <rect width="800" height="800" rx="176" fill="var(--color-noche, #242c3f)" />
        <g transform="translate(60 129) scale(0.85)">
          <YnaraSymbol variant="mono-light" idPrefix={id} />
        </g>
      </svg>
    );
  }

  return (
    <svg
      viewBox="0 0 800 700"
      width={size}
      height={size}
      role="img"
      aria-label={title}
      className={className}
    >
      <YnaraSymbol variant={variant} idPrefix={id} />
    </svg>
  );
}
