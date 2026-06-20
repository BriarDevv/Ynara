"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { cn } from "@/lib/cn";

type Props = {
  /** Caption opcional encima del title (text-caption, ink-soft). */
  eyebrow?: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Slot opcional al pie (StepFooter). */
  footer?: ReactNode;
  /**
   * Step "hero" (primera impresión): el title usa `text-display` (poster
   * editorial 42→56px) en vez de `text-title`. Reservado para el step `auth`
   * — DESIGN.md §4 / comentario de `.text-display` en globals.
   */
  hero?: boolean;
  className?: string;
};

/**
 * Container del contenido de un step. Aplica:
 *  - Mobile: max-width 480, padding cómodo (px-6 py-8).
 *  - Desktop (≥640): max-width 560, padding extra (px-10 py-14) y más
 *    aire vertical entre header / body. NO usamos card blanca en
 *    desktop — el lenguaje del onboarding es "papel sobre canvas
 *    ivory + LivingField"; un card-in-card mata la respiración.
 *  - Header con jerarquía clara: eyebrow opcional → title (ink-deep) →
 *    subtitle (ink-soft).
 *  - Animación de entrada `anim-fade-up` (respeta prefers-reduced-motion
 *    + override del a11y store).
 */
export function StepShell({
  eyebrow,
  title,
  subtitle,
  children,
  footer,
  hero = false,
  className,
}: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Al montar un step nuevo, llevar el foco a su título (tabIndex -1) para que
  // teclado y lector de pantalla no queden en el <body> tras navegar — y el SR
  // anuncie el título del paso. Si un input con autoFocus (auth/nombre) ya tomó
  // el foco, no se lo robamos.
  useEffect(() => {
    const active = document.activeElement;
    if (!active || active === document.body) {
      headingRef.current?.focus();
    }
  }, []);

  return (
    <div
      /*
       * Mobile (≤640): full-width column sobre canvas ivory, sin card.
       * Desktop (≥640): se vuelve card blanca con shadow-soft + radius-lg
       * + margen vertical para separar del header sticky. Resuelve el
       * "sparse" de columna angosta sobre canvas; la card ancla el
       * contenido y deja el fondo vivo visible alrededor.
       */
      className={cn(
        "anim-fade-up mx-auto flex w-full max-w-[480px] flex-1 flex-col gap-10 px-6 py-8",
        "sm:my-10 sm:max-w-[560px] sm:rounded-[var(--radius-lg)] sm:bg-[var(--color-bg)] sm:px-12 sm:py-12 sm:shadow-soft",
        className,
      )}
    >
      <header className="flex flex-col gap-3">
        {eyebrow ? <p className="text-caption text-[var(--color-ink-soft)]">{eyebrow}</p> : null}
        {/* Template literal (no cn): tailwind-merge trataría `text-display`/
            `text-title` y `text-[var(--color-ink-deep)]` como `text-*` en
            conflicto y descartaría el de tamaño. */}
        <h1
          ref={headingRef}
          tabIndex={-1}
          className={`${hero ? "text-display" : "text-title"} text-[var(--color-ink-deep)] outline-none focus-visible:shadow-none`}
        >
          {title}
        </h1>
        {subtitle ? <p className="text-body text-[var(--color-ink-soft)]">{subtitle}</p> : null}
      </header>
      <div className="flex flex-1 flex-col gap-6">{children}</div>
      {footer ? <div className="pt-2">{footer}</div> : null}
    </div>
  );
}
