import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Slot opcional al pie (StepFooter). */
  footer?: ReactNode;
  className?: string;
};

/**
 * Container del contenido de un step. Aplica:
 *  - max-width 480px (mobile-first; en desktop centrado, no se ensancha).
 *  - Padding consistente entre steps.
 *  - Animación de entrada `anim-fade-up` (respeta prefers-reduced-motion
 *    + override del a11y store).
 */
export function StepShell({ title, subtitle, children, footer, className }: Props) {
  return (
    <div
      className={cn(
        "anim-fade-up mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-8 px-6 py-8",
        className,
      )}
    >
      <header className="flex flex-col gap-2">
        <h1 className="text-title">{title}</h1>
        {subtitle ? <p className="text-body text-[var(--color-ink-soft)]">{subtitle}</p> : null}
      </header>
      <div className="flex flex-1 flex-col gap-6">{children}</div>
      {footer ? <div className="pt-2">{footer}</div> : null}
    </div>
  );
}
