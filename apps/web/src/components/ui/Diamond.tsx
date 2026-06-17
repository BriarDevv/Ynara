import { cn } from "@/lib/cn";

type Props = {
  /** Tamaño del lado del cuadrado antes de rotar (en px). Default: 10. */
  size?: number;
  /** Color de relleno / borde. Default: `currentColor`. */
  color?: string;
  /** Variante: sólido (default) u outline. */
  variant?: "solid" | "outline";
  className?: string;
};

/**
 * Diamante decorativo — cuadrado rotado 45°, sólido u outline.
 * Bullet de los insights del Recap (§3.4) y uso libre. Sin gradiente.
 */
export function Diamond({
  size = 10,
  color = "currentColor",
  variant = "solid",
  className,
}: Props) {
  const style =
    variant === "outline" ? { border: `1.5px solid ${color}` } : { backgroundColor: color };

  return (
    <span
      aria-hidden
      className={cn("inline-block shrink-0 rotate-45", className)}
      style={{ width: size, height: size, borderRadius: Math.max(1, size * 0.12), ...style }}
    />
  );
}
