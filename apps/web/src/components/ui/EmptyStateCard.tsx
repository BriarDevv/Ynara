import { MemoryField } from "@ynara/ui";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = {
  title: string;
  hint?: string;
  action?: ReactNode;
  /**
   * Fondo de "Red de memoria" (DESIGN.md §2) detrás del contenido. Opt-in
   * (default false) para no alterar los callers existentes que lo usan pelado.
   */
  field?: boolean;
  className?: string;
};

export function EmptyStateCard({ title, hint, action, field = false, className }: Props) {
  return (
    <div
      className={cn(
        "relative flex flex-col items-center gap-3 overflow-hidden rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-soft)] px-8 py-10 text-center",
        className,
      )}
    >
      {field ? (
        // Ambiente detrás del texto (§2.5: nunca tapar el contenido). El propio
        // MemoryField ya mantiene opacidades bajas; lo dejamos sutil.
        <span aria-hidden className="pointer-events-none absolute inset-0 opacity-60">
          <MemoryField density="dispersa" />
        </span>
      ) : null}
      <div className="relative flex flex-col items-center gap-3">
        <p className="text-body text-[var(--color-ink-soft)]">{title}</p>
        {hint ? <p className="text-body-sm text-[var(--color-ink-muted)]">{hint}</p> : null}
        {action ? <div className="mt-2">{action}</div> : null}
      </div>
    </div>
  );
}
