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
  interactive:
    "shadow-soft cursor-pointer transition-[transform,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] hover:shadow-lifted hover:-translate-y-[1px]",
};

export function Card({ variant = "default", children, className, ...rest }: Props) {
  return (
    <div className={cn(BASE, VARIANTS[variant], className)} {...rest}>
      {children}
    </div>
  );
}
