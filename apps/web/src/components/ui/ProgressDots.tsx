import { cn } from "@/lib/cn";

type Props = {
  total: number;
  current: number;
  className?: string;
  ariaLabel?: string;
};

type Dot = {
  id: string;
  active: boolean;
  isCurrent: boolean;
};

/**
 * Genera N dots con ids `dot-0`..`dot-N`. La lista nunca se reordena
 * (la cantidad y el orden son función pura de `total`), así que usar el
 * índice como parte del id es semánticamente correcto y estable —
 * no es un workaround de una key-reordering issue.
 */
function buildDots(total: number, current: number): Dot[] {
  return Array.from({ length: total }, (_, i) => ({
    id: `dot-${i}`,
    active: i <= current,
    isCurrent: i === current,
  }));
}

export function ProgressDots({ total, current, className, ariaLabel = "Progreso" }: Props) {
  const dots = buildDots(total, current);
  return (
    <div
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={Math.max(1, Math.min(total, current + 1))}
      className={cn("flex items-center gap-2", className)}
    >
      {dots.map((dot) => (
        <span
          key={dot.id}
          aria-hidden
          className={cn(
            // Solo transicionamos el color (regla del repo: no animar width —
            // dispara reflow por frame). El cambio de ancho del dot activo es
            // instantáneo (snap); el color sí se atenúa suave.
            "h-1.5 rounded-[var(--radius-pill)] transition-[background-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)]",
            dot.isCurrent
              ? /*
                 * Azul plano de marca (--color-blue-flat). Antes era el
                 * gradiente azul saturado, que peleaba con el canvas
                 * ivory + el fondo vivo; con plano se lee como acento,
                 * no como CTA pegado al header.
                 */
                "bg-[var(--color-blue-flat)] w-8"
              : dot.active
                ? "w-1.5 bg-[var(--color-ink-deep)]"
                : "w-1.5 bg-[var(--color-ink-faint)]",
          )}
        />
      ))}
    </div>
  );
}
