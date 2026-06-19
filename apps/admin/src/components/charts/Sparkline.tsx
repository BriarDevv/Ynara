import { cn } from "@/lib/cn";
import { sparklinePath } from "./chart-utils";

type Props = {
  /** Serie de valores a dibujar (orden cronológico ascendente). */
  data: number[];
  /** Ancho del `viewBox` (no del render; se estira con el contenedor). */
  width?: number;
  /** Alto del `viewBox`. */
  height?: number;
  /** Descripción accesible obligatoria (el SVG es la única semántica). */
  "aria-label": string;
  className?: string;
};

/**
 * Línea de tendencia minimalista: un `path` azul plano de 1.5px, sin ejes, sin
 * relleno, sin números. `viewBox` normalizado + `preserveAspectRatio="none"`
 * para que se estire al ancho de su contenedor (típicamente dentro de un
 * `KpiCard`). Color por token (`--color-azul`), nunca gradiente.
 */
export function Sparkline({
  data,
  width = 120,
  height = 32,
  "aria-label": ariaLabel,
  className,
}: Props) {
  const d = sparklinePath(data, width, height);
  return (
    <svg
      role="img"
      aria-label={ariaLabel}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={cn("h-8 w-full overflow-visible", className)}
    >
      <path
        d={d}
        fill="none"
        stroke="var(--color-azul)"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
