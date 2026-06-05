import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = {
  /** Caption opcional encima del title (text-caption, ink-muted). */
  eyebrow?: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Slot opcional al pie (StepFooter). */
  footer?: ReactNode;
  className?: string;
};

/**
 * Container del contenido de un step. Aplica:
 *  - Mobile: max-width 480, padding cómodo (px-6 py-8).
 *  - Desktop (≥640): max-width 560, padding extra (px-10 py-14) y más
 *    aire vertical entre header / body. NO usamos card blanca en
 *    desktop — el lenguaje del onboarding es "papel sobre canvas
 *    ivory + BrandWaves"; un card-in-card mata la respiración.
 *  - Header con jerarquía clara: eyebrow opcional → title (ink-deep) →
 *    subtitle (ink-soft).
 *  - Animación de entrada `anim-fade-up` (respeta prefers-reduced-motion
 *    + override del a11y store).
 */
export function StepShell({ eyebrow, title, subtitle, children, footer, className }: Props) {
  return (
    <div
      /*
       * Mobile (≤640): full-width column sobre canvas ivory, sin card.
       * Desktop (≥640): se vuelve card blanca con shadow-soft + radius-lg
       * + margen vertical para separar del header sticky. Resuelve el
       * "sparse" de columna angosta sobre canvas; la card ancla el
       * contenido y deja BrandWaves visible alrededor.
       */
      className={cn(
        "anim-fade-up mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-10 px-6 py-8",
        "sm:my-10 sm:max-w-[560px] sm:rounded-[var(--radius-lg)] sm:bg-[var(--color-bg)] sm:px-12 sm:py-12 sm:shadow-soft",
        className,
      )}
    >
      <header className="flex flex-col gap-3">
        {eyebrow ? <p className="text-caption text-[var(--color-ink-muted)]">{eyebrow}</p> : null}
        <h1 className="text-title text-[var(--color-ink-deep)]">{title}</h1>
        {subtitle ? <p className="text-body text-[var(--color-ink-soft)]">{subtitle}</p> : null}
      </header>
      <div className="flex flex-1 flex-col gap-6">{children}</div>
      {footer ? <div className="pt-2">{footer}</div> : null}
    </div>
  );
}
