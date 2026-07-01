import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "outline" | "ghost";
type Size = "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 rounded-[var(--r-pill)] font-medium transition-all duration-[var(--dur-fast)] [transition-timing-function:var(--ease-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50";

const variants: Record<Variant, string> = {
  // Azul plano — el ÚNICO acento de la marca.
  primary:
    "bg-blue text-white shadow-[var(--glow-blue)] hover:bg-blue-hover hover:-translate-y-0.5 active:translate-y-0 active:bg-blue-active",
  outline:
    "border border-[var(--c-hair-strong)] text-text hover:border-[var(--c-acc)] hover:bg-white/5",
  ghost: "text-text-soft hover:text-text hover:bg-white/5",
};

const sizes: Record<Size, string> = {
  md: "h-11 px-5 text-[0.9375rem]",
  lg: "h-[3.25rem] px-7 text-[1.0625rem]",
};

type Props = {
  children: ReactNode;
  href?: string;
  variant?: Variant;
  size?: Size;
  className?: string;
  target?: string;
  rel?: string;
  type?: "button" | "submit";
  ariaLabel?: string;
  onClick?: () => void;
};

export function Button({
  children,
  href,
  variant = "primary",
  size = "md",
  className,
  target,
  rel,
  type = "button",
  ariaLabel,
  onClick,
}: Props) {
  const cls = cn(base, variants[variant], sizes[size], className);

  if (href) {
    return (
      <a
        href={href}
        target={target}
        rel={rel}
        aria-label={ariaLabel}
        onClick={onClick}
        className={cls}
      >
        {children}
      </a>
    );
  }

  return (
    <button type={type} aria-label={ariaLabel} onClick={onClick} className={cls}>
      {children}
    </button>
  );
}
