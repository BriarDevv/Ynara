import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "subtle";

type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> & {
  variant?: Variant;
  fullWidth?: boolean;
  children: ReactNode;
  className?: string;
};

/*
 * Base común a todas las variants. La altura efectiva sale de `py-3` +
 * `leading` del text-button → ~44px, dentro del rango Apple/WCAG para
 * targets táctiles. `active:scale-[0.98]` es un feedback de press; respeta
 * prefers-reduced-motion vía la transición global de globals.css.
 */
const BASE =
  "text-button inline-flex items-center justify-center gap-2 rounded-[var(--radius-md)] transition-[background-color,color,transform,opacity,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]";

/*
 * - primary: azul plano de marca (no gradient). El gradient saturado
 *   quedaba "genérico de SaaS"; el plano + shadow-soft se lee más sobrio
 *   y deja el gradiente para acentos puntuales (ProgressDots, hairline).
 * - secondary: outline en ink, fondo transparent. CTA secundario en
 *   pantallas con primary.
 * - ghost: sin fondo en reposo. Para "Atrás", "Cancelar".
 * - subtle: text-link sobrio. Para acciones tipo "Probar sin cuenta",
 *   "Olvidé mi contraseña". Hover sube el ink y suma underline.
 */
const VARIANTS: Record<Variant, string> = {
  primary:
    "px-6 py-3 text-[var(--color-on-dark)] bg-[var(--color-blue-flat)] shadow-soft hover:bg-[var(--color-blue-flat-hover)] active:bg-[var(--color-blue-flat-active)] disabled:hover:bg-[var(--color-blue-flat)]",
  secondary:
    "px-6 py-3 text-[var(--color-ink)] bg-transparent border border-[var(--color-border-strong)] hover:bg-[var(--color-bg-soft)] hover:border-[var(--color-ink)]",
  ghost:
    "px-4 py-3 text-[var(--color-ink-soft)] bg-transparent hover:text-[var(--color-ink)] hover:bg-[var(--color-bg-soft)]",
  subtle:
    "px-1 py-1 text-[var(--color-ink-soft)] bg-transparent underline underline-offset-4 decoration-[var(--color-ink-faint)] hover:text-[var(--color-ink)] hover:decoration-[var(--color-ink-soft)] active:scale-100",
};

export function Button({
  variant = "primary",
  fullWidth = false,
  children,
  className,
  type = "button",
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={cn(BASE, VARIANTS[variant], fullWidth && "w-full", className)}
      {...rest}
    >
      {children}
    </button>
  );
}
