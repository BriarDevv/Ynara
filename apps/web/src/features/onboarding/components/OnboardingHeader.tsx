"use client";

import { type KeyboardEvent, useEffect, useRef, useState } from "react";
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
 */
export function OnboardingHeader({ total, current, onSkipAll, className }: Props) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const closeDialog = () => {
    setConfirmOpen(false);
    // Devolver foco al botón "Saltar" tras cerrar (a11y).
    requestAnimationFrame(() => triggerRef.current?.focus());
  };

  return (
    <header className={cn("flex items-center justify-between gap-4 px-6 py-4", className)}>
      <YnaraMark size={32} title="Ynara" />
      <ProgressDots total={total} current={current} ariaLabel="Progreso del onboarding" />
      {onSkipAll ? (
        <>
          <Button
            ref={triggerRef}
            variant="ghost"
            onClick={() => setConfirmOpen(true)}
            className="text-body-sm"
          >
            Saltar
          </Button>
          {confirmOpen ? (
            <SkipConfirmDialog
              onCancel={closeDialog}
              onConfirm={() => {
                setConfirmOpen(false);
                onSkipAll();
              }}
            />
          ) : null}
        </>
      ) : (
        <span aria-hidden className="w-[64px]" />
      )}
    </header>
  );
}

/**
 * Dialog modal con focus trap manual.
 *
 * Implementa el patrón mínimo WAI-ARIA Dialog:
 *  - Focus inicial en el primer botón al abrir.
 *  - Tab y Shift+Tab navegan ciclicamente entre los botones del dialog.
 *  - Escape cierra (mismo handler que Cancel).
 *  - Click en backdrop NO cierra: el usuario debe elegir explícito
 *    "Volver" o "Saltar igual" — evita cierre accidental con consecuencias.
 */
function SkipConfirmDialog({
  onCancel,
  onConfirm,
}: {
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== "Tab") return;

    const focusables = [cancelRef.current, confirmRef.current].filter(
      (el): el is HTMLButtonElement => el !== null,
    );
    if (focusables.length === 0) return;

    const active =
      document.activeElement instanceof HTMLButtonElement ? document.activeElement : null;
    const currentIndex = active ? focusables.indexOf(active) : -1;
    const nextIndex = event.shiftKey
      ? (currentIndex - 1 + focusables.length) % focusables.length
      : (currentIndex + 1) % focusables.length;

    event.preventDefault();
    focusables[nextIndex]?.focus();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="skip-title"
      onKeyDown={handleKeyDown}
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--color-overlay)] p-6"
    >
      <div className="anim-fade-up flex w-full max-w-[420px] flex-col gap-4 rounded-[var(--radius-lg)] bg-[var(--color-bg)] p-6 shadow-lifted">
        <h2 id="skip-title" className="text-subtitle">
          ¿Saltar el onboarding?
        </h2>
        <p className="text-body text-[var(--color-ink-soft)]">
          Voy a empezar sin conocerte. Lo podés completar más tarde desde Ajustes.
        </p>
        <div className="mt-2 flex justify-end gap-2">
          <Button ref={cancelRef} variant="ghost" onClick={onCancel}>
            Volver
          </Button>
          <Button ref={confirmRef} variant="secondary" onClick={onConfirm}>
            Saltar igual
          </Button>
        </div>
      </div>
    </div>
  );
}
