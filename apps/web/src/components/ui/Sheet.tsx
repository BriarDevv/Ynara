"use client";

import { Icon } from "@ynara/ui";
import { type ReactNode, useEffect, useId, useRef } from "react";
import { cn } from "@/lib/cn";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Título accesible. Si `titleHidden`, va solo para el lector de pantalla. */
  title: string;
  titleHidden?: boolean;
  description?: string;
  children: ReactNode;
  className?: string;
};

/**
 * Sheet reutilizable (DESIGN.md §6/§7, build-plan §3.1): **bottom-sheet** en
 * mobile (`<sm`, con handle 40×4 y esquinas superiores redondeadas) y **modal
 * centrado** en `sm+`. Pensado para Mode Switcher (12), Check-in (14) y Recap
 * (15) — todavía sin cablear (Fase H); acá va el primitive + showcase.
 *
 * Sobre `HTMLDialogElement` + `showModal()`: el browser provee focus-trap,
 * Escape y devolución de foco al disparador, gratis. El `<dialog>` queda
 * siempre montado y se abre/cierra por la prop `open`; el contenido interior
 * se renderiza sólo cuando está abierto, así la animación de entrada corre en
 * cada apertura. Esc y click en el backdrop (fuera del panel) cierran vía
 * `onClose`.
 */
export function Sheet({
  open,
  onClose,
  title,
  titleHidden = false,
  description,
  children,
  className,
}: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descId = useId();

  // Sincroniza el estado nativo del <dialog> con la prop `open`.
  useEffect(() => {
    const node = dialogRef.current;
    if (!node) return;
    if (open && !node.open) node.showModal();
    else if (!open && node.open) node.close();
  }, [open]);

  // Cierra al desmontar (evita un <dialog> abierto huérfano).
  useEffect(() => {
    const node = dialogRef.current;
    return () => {
      if (node?.open) node.close();
    };
  }, []);

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: Escape cierra vía onCancel; el click en el backdrop es enhancement de mouse, no la única vía de cierre.
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      onClick={(event) => {
        // Backdrop = cualquier click que no cayó dentro del panel.
        if (!panelRef.current?.contains(event.target as Node)) onClose();
      }}
      onCancel={(event) => {
        // Escape dispara `cancel`: prevenimos el close nativo para que el
        // unmount lo controle el caller vía `open`.
        event.preventDefault();
        onClose();
      }}
      className="m-0 h-full max-h-full w-full max-w-full bg-transparent p-0 backdrop:bg-[var(--color-overlay)]"
    >
      {open ? (
        <div className="flex h-full w-full items-end justify-center sm:items-center sm:p-4">
          <div
            ref={panelRef}
            className={cn(
              "anim-fade-up relative flex max-h-[85vh] w-full flex-col overflow-y-auto rounded-t-[var(--radius-xl)] bg-[var(--color-bg)] p-6 shadow-lifted",
              "sm:max-h-[80vh] sm:w-full sm:max-w-[480px] sm:rounded-[var(--radius-lg)]",
              className,
            )}
          >
            {/* Botón de cierre visible: hasta ahora el cierre dependía solo de
                Escape o click en el backdrop, invisibles para mouse/touch. */}
            <button
              type="button"
              onClick={onClose}
              aria-label="Cerrar"
              className="absolute right-3 top-3 z-10 flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] text-[var(--color-ink-soft)] transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-bg-soft)] hover:text-[var(--color-ink)]"
            >
              <Icon name="cerrar" size={18} />
            </button>
            <div
              aria-hidden
              className="mx-auto mb-4 h-1 w-10 rounded-full bg-[var(--color-border-strong)] sm:hidden"
            />
            <h2
              id={titleId}
              className={cn("text-subtitle text-[var(--color-ink)]", titleHidden && "sr-only")}
            >
              {title}
            </h2>
            {description ? (
              <p id={descId} className="text-body-sm mt-1 text-[var(--color-ink-soft)]">
                {description}
              </p>
            ) : null}
            <div className="mt-4">{children}</div>
          </div>
        </div>
      ) : null}
    </dialog>
  );
}
