import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = {
  title: string;
  hint?: string;
  action?: ReactNode;
  className?: string;
};

export function EmptyStateCard({ title, hint, action, className }: Props) {
  return (
    <div
      className={cn(
        "relative flex flex-col items-center gap-3 overflow-hidden rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)] px-8 py-10 text-center",
        className,
      )}
    >
      <p className="text-body text-[var(--color-ink-soft)]">{title}</p>
      {hint ? <p className="text-body-sm text-[var(--color-ink-muted)]">{hint}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
