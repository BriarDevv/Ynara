import type { HTMLAttributes, ReactNode } from "react";

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
  const classes = [BASE, VARIANTS[variant], className ?? ""].filter(Boolean).join(" ");

  return (
    <div className={classes} {...rest}>
      {children}
    </div>
  );
}
