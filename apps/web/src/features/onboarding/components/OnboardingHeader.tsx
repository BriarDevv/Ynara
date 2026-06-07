"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ProgressDots } from "@/components/ui/ProgressDots";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { cn } from "@/lib/cn";

type Props = {
  total: number;
  current: number;
  onSkipAll?: () => void;
  className?: string;
};

/**
 * Header sticky del onboarding: YnaraMark + ProgressDots + "Saltar"
 * discreto. "Saltar onboarding" abre un modal de confirmación (no es
 * un skip por step, ver §4.8 del plan).
 *
 * Layout: contenedor centrado (max-w 640) con mismo eje que el StepShell.
 * Background semi-transparente con `backdrop-blur-sm` para que el campo
 * vivo del layout se atenúe detrás del header sin ocultarse del todo.
 * `sticky top-0 z-20` lo deja ahí mientras se scrollea.
 */
export function OnboardingHeader({ total, current, onSkipAll, className }: Props) {
  const [confirmOpen, setConfirmOpen] = useState(false);

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
        {onSkipAll ? (
          <>
            <Button variant="subtle" onClick={() => setConfirmOpen(true)} className="text-body-sm">
              Saltar
            </Button>
            {confirmOpen ? (
              <SkipConfirmDialog
                onCancel={() => setConfirmOpen(false)}
                onConfirm={() => {
                  setConfirmOpen(false);
                  onSkipAll();
                }}
              />
            ) : null}
          </>
        ) : (
          /* Spacer del mismo ancho aprox que el botón "Saltar" para que el
             ProgressDots quede centrado óptico. */
          <span aria-hidden className="w-[52px]" />
        )}
      </div>
    </header>
  );
}

/**
 * Confirmación de "saltar onboarding".
 *
 * Implementado con `HTMLDialogElement` + `showModal()`: el browser provee
 * focus trap, manejo de Escape y devolución de focus al elemento que tenía
 * focus antes de abrir (el botón "Saltar"). El click en el backdrop cierra
 * detectando que el target del evento es el propio `<dialog>` (no su
 * contenido interior).
 */
function SkipConfirmDialog({
  onCancel,
  onConfirm,
}: {
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const node = dialogRef.current;
    if (!node) return;
    if (!node.open) node.showModal();
    return () => {
      if (node.open) node.close();
    };
  }, []);

  const handleBackdropClick = (event: React.MouseEvent<HTMLDialogElement>) => {
    // Si el click cayó directamente en el <dialog> (no en su contenido
    // interior), es click en el backdrop → cerrar.
    if (event.target === dialogRef.current) onCancel();
  };

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: Escape cierra vía onCancel; el click en el backdrop es enhancement de mouse, no la única vía de cierre.
    <dialog
      ref={dialogRef}
      aria-modal="true"
      aria-labelledby="skip-title"
      onClick={handleBackdropClick}
      onCancel={(event) => {
        // Escape dispara `cancel` → prevenir el close default para que
        // React controle el unmount vía `confirmOpen`.
        event.preventDefault();
        onCancel();
      }}
      className="m-0 max-h-full max-w-full bg-transparent p-0 backdrop:bg-[var(--color-overlay)]"
    >
      <div className="anim-fade-up flex w-full max-w-[420px] flex-col gap-4 rounded-[var(--radius-lg)] bg-[var(--color-bg)] p-6 shadow-lifted">
        <h2 id="skip-title" className="text-subtitle text-[var(--color-ink-deep)]">
          ¿Saltar el onboarding?
        </h2>
        <p className="text-body text-[var(--color-ink-soft)]">
          Voy a empezar sin conocerte. Lo podés completar más tarde desde Ajustes.
        </p>
        <div className="mt-2 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Volver
          </Button>
          <Button variant="secondary" onClick={onConfirm}>
            Saltar igual
          </Button>
        </div>
      </div>
    </dialog>
  );
}
