import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "default" | "interactive";

type Props = HTMLAttributes<HTMLDivElement> & {
  variant?: Variant;
  children: ReactNode;
};

const BASE =
  "bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[var(--radius-lg)] p-6";

const VARIANTS: Record<Variant, string> = {
  default: "",
  // Microinteracción §8.2: hover scale(1.02) + elevación, a 150ms (--duration-fast).
  interactive:
    "shadow-soft cursor-pointer transition-[transform,box-shadow] duration-[var(--duration-fast)] ease-[var(--ease-out-soft)] hover:shadow-lifted hover:scale-[1.02]",
};

export function Card({ variant = "default", children, className, ...rest }: Props) {
  return (
    <div className={cn(BASE, VARIANTS[variant], className)} {...rest}>
      {children}
    </div>
  );
}
