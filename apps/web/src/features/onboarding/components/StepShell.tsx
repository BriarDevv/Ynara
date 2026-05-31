import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "standard" | "editorial";

type Props = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Slot opcional al pie (StepFooter). */
  footer?: ReactNode;
  /**
   * "standard" (default) usa `.text-title`. "editorial" usa `.text-display`
   * para las piezas de marca (auth, outro) — big type estilo poster (§4).
   */
  variant?: Variant;
  /**
   * Slot de fondo detrás del contenido (ej. `MemoryField`). Se pinta como
   * ambiente (absolute, no captura punteros); el contenido va por encima.
   */
  background?: ReactNode;
  className?: string;
};

/**
 * Container del contenido de un step. Aplica:
 *  - max-width 480px (mobile-first; en desktop centrado, no se ensancha).
 *  - Padding consistente entre steps.
 *  - Animación de entrada `anim-fade-up` (respeta prefers-reduced-motion
 *    + override del a11y store).
 */
export function StepShell({
  title,
  subtitle,
  children,
  footer,
  variant = "standard",
  background,
  className,
}: Props) {
  return (
    <div
      className={cn(
        "anim-fade-up mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-8 px-6 py-8",
        background ? "relative overflow-hidden" : null,
        className,
      )}
    >
      {background ? (
        <div aria-hidden className="pointer-events-none absolute inset-0">
          {background}
        </div>
      ) : null}
      <header className={cn("flex flex-col gap-2", background ? "relative" : null)}>
        <h1 className={variant === "editorial" ? "text-display" : "text-title"}>{title}</h1>
        {subtitle ? <p className="text-body text-[var(--color-ink-soft)]">{subtitle}</p> : null}
      </header>
      <div className={cn("flex flex-1 flex-col gap-6", background ? "relative" : null)}>
        {children}
      </div>
      {footer ? <div className={cn("pt-2", background ? "relative" : null)}>{footer}</div> : null}
    </div>
  );
}
