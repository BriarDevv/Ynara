"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODES, type ModeId } from "@/components/ui/modes";
import { cn } from "@/lib/cn";

type Props = {
  /** Modos que el usuario eligió en el onboarding. */
  interestedModes: readonly ModeId[];
  activeMode: ModeId;
  onChange: (mode: ModeId) => void;
  className?: string;
};

/**
 * Selector de modo del home (plan §5.4). El dropdown muestra primero los
 * modos elegidos (seleccionables, con su ModeChip) y al final los no
 * elegidos, grisados con un CTA "Activar en Ajustes" (deshabilitados acá).
 */
export function ModeSwitcher({ interestedModes, activeMode, onChange, className }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  // Cierra al click afuera o con Escape.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const inactiveModes = MODES.filter((m) => !interestedModes.includes(m.id));
  const select = (mode: ModeId) => {
    onChange(mode);
    setOpen(false);
  };

  return (
    <div ref={rootRef} className={cn("relative w-fit", className)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-[var(--radius-pill)] border border-[var(--color-border)] bg-[var(--color-bg)] py-1.5 pr-3 pl-1.5 transition-colors duration-[var(--duration-base)] ease-[var(--ease-out-soft)] hover:border-[var(--color-border-strong)]"
      >
        <ModeChip modeId={activeMode} size="sm" />
        <span aria-hidden className="text-body-sm text-[var(--color-ink-muted)]">
          ▾
        </span>
      </button>

      {open ? (
        // Disclosure simple: una lista de botones enlazada al trigger por
        // aria-controls, no un role="menu" (que exigiría navegación por
        // flechas + roles menuitem). aria-pressed marca el modo activo; los
        // no activados van aria-disabled.
        <div
          id={panelId}
          className="anim-fade-up absolute left-0 top-[calc(100%+8px)] z-40 flex w-60 flex-col gap-1 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg)] p-2 shadow-lifted"
        >
          {interestedModes.map((id) => (
            <button
              key={id}
              type="button"
              aria-pressed={id === activeMode}
              onClick={() => select(id)}
              className={cn(
                "flex items-center gap-2 rounded-[var(--radius-sm)] px-2 py-2 text-left transition-colors duration-[var(--duration-base)] ease-[var(--ease-out-soft)] hover:bg-[var(--color-bg-soft)]",
                id === activeMode && "bg-[var(--color-bg-soft)]",
              )}
            >
              <ModeChip modeId={id} size="sm" />
              {id === activeMode ? (
                <span aria-hidden className="ml-auto text-[var(--color-accent)]">
                  ✓
                </span>
              ) : null}
            </button>
          ))}

          {inactiveModes.length > 0 ? (
            <>
              <div className="my-1 h-px bg-[var(--color-border)]" />
              <p className="px-2 py-1 text-caption text-[var(--color-ink-muted)]">No activados</p>
              {inactiveModes.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  aria-disabled="true"
                  tabIndex={-1}
                  title="Activá este modo desde Ajustes"
                  onClick={(e) => e.preventDefault()}
                  className="flex items-center gap-2 rounded-[var(--radius-sm)] px-2 py-2 text-left opacity-50"
                >
                  <ModeChip modeId={mode.id} size="sm" />
                  <span className="ml-auto text-caption text-[var(--color-ink-muted)]">
                    Activar en Ajustes
                  </span>
                </button>
              ))}
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
