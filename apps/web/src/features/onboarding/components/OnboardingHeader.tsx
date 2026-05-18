"use client";

import { useState } from "react";
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

  return (
    <header className={cn("flex items-center justify-between gap-4 px-6 py-4", className)}>
      <YnaraMark size={32} title="Ynara" />
      <ProgressDots total={total} current={current} ariaLabel="Progreso del onboarding" />
      {onSkipAll ? (
        <>
          <Button variant="ghost" onClick={() => setConfirmOpen(true)} className="text-body-sm">
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
        <span aria-hidden className="w-[64px]" />
      )}
    </header>
  );
}

function SkipConfirmDialog({
  onCancel,
  onConfirm,
}: {
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="skip-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgb(36_44_63_/_0.4)] p-6"
    >
      <div className="anim-fade-up flex w-full max-w-[420px] flex-col gap-4 rounded-[var(--radius-lg)] bg-[var(--color-bg)] p-6 shadow-lifted">
        <h2 id="skip-title" className="text-subtitle">
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
    </div>
  );
}
