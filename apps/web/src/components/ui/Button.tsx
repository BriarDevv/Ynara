import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost";

type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> & {
  variant?: Variant;
  fullWidth?: boolean;
  children: ReactNode;
  className?: string;
};

const BASE =
  "text-button inline-flex items-center justify-center gap-2 px-6 py-[14px] rounded-[var(--radius-md)] transition-[transform,opacity,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]";

const VARIANTS: Record<Variant, string> = {
  primary: "text-[var(--color-on-dark)] bg-gradient-blue-base shadow-soft hover:shadow-lifted",
  secondary:
    "text-[var(--color-ink)] bg-transparent border border-[var(--color-border-strong)] hover:bg-[var(--color-bg-soft)]",
  ghost:
    "text-[var(--color-ink-soft)] bg-transparent hover:text-[var(--color-ink)] hover:bg-[var(--color-bg-soft)]",
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
