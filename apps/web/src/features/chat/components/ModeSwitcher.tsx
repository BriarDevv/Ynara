"use client";

import { useRouter } from "next/navigation";
import { MODES, type ModeId } from "@/components/ui/modes";
import { Sheet } from "@/components/ui/Sheet";
import { useChatStore } from "@/features/chat/store";
import { cn } from "@/lib/cn";

/**
 * Sheet para cambiar de modo desde el header de la conversación (chat plan
 * §4.4 / W5). Como **una sesión = un modo**, elegir un modo distinto arranca
 * una sesión NUEVA y navega a ella; la conversación actual se conserva en el
 * store (se retoma desde la landing), así que no hay nada que confirmar. Elegir
 * el modo actual solo cierra.
 */
export function ModeSwitcher({
  open,
  onClose,
  currentMode,
}: {
  open: boolean;
  onClose: () => void;
  currentMode: ModeId;
}) {
  const router = useRouter();
  const createSession = useChatStore((s) => s.createSession);

  const pick = (mode: ModeId) => {
    if (mode === currentMode) {
      onClose();
      return;
    }
    const id = createSession(mode);
    onClose();
    router.push(`/chat/${id}`);
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Cambiar de modo"
      description="Cada modo arranca una conversación nueva. La actual queda guardada."
    >
      <ul className="flex flex-col gap-2">
        {MODES.map((mode) => {
          const active = mode.id === currentMode;
          return (
            <li key={mode.id}>
              <button
                type="button"
                onClick={() => pick(mode.id)}
                aria-current={active ? "true" : undefined}
                className={cn(
                  "flex w-full items-center gap-3 rounded-[var(--radius-lg)] border bg-[var(--color-bg)] p-4 text-left transition-colors hover:bg-[var(--color-bg-soft)]",
                  active ? "border-[var(--color-ink)]" : "border-[var(--color-border)]",
                )}
              >
                <span
                  aria-hidden
                  className="h-3 w-3 shrink-0 rounded-[var(--radius-pill)]"
                  style={{ backgroundColor: mode.tintVar }}
                />
                <span className="flex flex-1 flex-col">
                  <span className="text-body font-semibold text-[var(--color-ink)]">
                    {mode.label}
                  </span>
                  <span className="text-body-sm text-[var(--color-ink-soft)]">{mode.blurb}</span>
                </span>
                {active ? (
                  <span className="text-caption text-[var(--color-ink-soft)]">Actual</span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
    </Sheet>
  );
}
