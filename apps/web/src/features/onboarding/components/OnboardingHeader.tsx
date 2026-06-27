"use client";

import { ProgressDots } from "@/components/ui/ProgressDots";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { cn } from "@/lib/cn";

type Props = {
  total: number;
  current: number;
  className?: string;
};

/**
 * Header sticky del onboarding: YnaraMark + ProgressDots centrado.
 *
 * Layout: contenedor centrado (max-w 640) con mismo eje que el StepShell.
 * Background semi-transparente con `backdrop-blur-md` para que el campo vivo
 * del layout se atenúe detrás sin ocultarse del todo. `sticky top-0 z-20` lo
 * deja fijo mientras se scrollea.
 */
export function OnboardingHeader({ total, current, className }: Props) {
  return (
    <header
      className={cn(
        "sticky top-0 z-20 w-full border-b border-[var(--color-border)]/40 bg-[color-mix(in_srgb,var(--color-bg-canvas)_82%,transparent)] backdrop-blur-md",
        className,
      )}
    >
      <div className="mx-auto flex w-full max-w-[640px] items-center justify-between gap-3 px-6 py-3.5 sm:px-10">
        <YnaraMark size={32} title="Ynara" />
        <ProgressDots total={total} current={current} ariaLabel="Progreso del onboarding" />
        {/* Spacer del ancho del YnaraMark para que el ProgressDots quede
            centrado óptico ahora que no hay botón "Saltar" a la derecha. */}
        <span aria-hidden className="w-8" />
      </div>
    </header>
  );
}
