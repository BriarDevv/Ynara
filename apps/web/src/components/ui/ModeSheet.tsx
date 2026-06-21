"use client";

import { isAgentMode } from "@ynara/core/features/chat";
import { Diamond } from "@/components/ui/Diamond";
import { MODES, type ModeId } from "@/components/ui/modes";
import { Sheet } from "@/components/ui/Sheet";
import { cn } from "@/lib/cn";
import { useActiveModeStore } from "@/stores/mode";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Modo marcado como actual (el activo global, o el de la sesión en el chat). */
  current: ModeId;
  /**
   * Side-effect opcional al elegir un modo, además de fijar el modo global.
   * Lo usa el chat para arrancar una conversación nueva en el modo elegido.
   */
  onAfterPick?: (mode: ModeId) => void;
  /**
   * Aviso opcional sobre la consecuencia de elegir un modo, mostrado arriba de
   * la lista. Lo usa el chat para avisar que cambiar de modo arranca una
   * conversación nueva (sienta la expectativa antes de elegir, no después).
   */
  note?: string;
};

/**
 * Picker de modo **único y compartido** (paridad con el mockup: el chip de Hoy,
 * el header del chat y el sidebar abren el mismo sheet). Elegir un modo fija el
 * **modo activo global** (`useActiveModeStore`), que re-tiñe toda la app vía
 * `useActiveMode` → `LivingField`/orbe/acentos. No crea sesiones por sí solo:
 * ese comportamiento extra lo inyecta el caller con `onAfterPick`.
 */
export function ModeSheet({ open, onClose, current, onAfterPick, note }: Props) {
  const setMode = useActiveModeStore((s) => s.setMode);

  const pick = (mode: ModeId) => {
    setMode(mode);
    onAfterPick?.(mode);
    onClose();
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Elegí cómo te acompaño"
      description="Ynara ajusta el tono, el foco y qué recuerda en cada modo."
    >
      {note ? (
        <p className="text-body-sm mb-2 rounded-[var(--radius-md)] bg-[var(--color-bg-soft)] px-3 py-2 text-[var(--color-ink-soft)]">
          {note}
        </p>
      ) : null}
      <ul className="flex flex-col">
        {MODES.map((mode, i) => {
          const on = mode.id === current;
          return (
            <li key={mode.id}>
              <button
                type="button"
                onClick={() => pick(mode.id)}
                aria-current={on ? "true" : undefined}
                className={cn(
                  "flex w-full items-center gap-3.5 py-3.5 text-left transition-colors duration-[var(--duration-fast)]",
                  i > 0 && "border-t border-[var(--color-border)]",
                )}
              >
                <span
                  aria-hidden
                  className="h-2.5 w-2.5 shrink-0 rounded-[var(--radius-pill)]"
                  style={{ backgroundColor: mode.tintVar }}
                />
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="flex items-center gap-2">
                    <span className="text-body font-semibold text-[var(--color-ink)]">
                      {mode.label}
                    </span>
                    {/* Micro-indicador de capacidad (derivado del routing real,
                        isAgentMode de @ynara/core): los modos agente actúan por
                        vos (ejecutan tools, escriben memoria); el resto solo
                        conversa. "Actúa por vos" en vez de "agenda" porque
                        Memoria es agente pero no toca el calendario. */}
                    <span className="text-caption shrink-0 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)] px-2 py-0.5 text-[var(--color-ink-soft)]">
                      {isAgentMode(mode.id) ? "Actúa por vos" : "Solo conversa"}
                    </span>
                  </span>
                  <span className="text-body-sm text-[var(--color-ink-soft)]">{mode.blurb}</span>
                </span>
                {on ? <Diamond size={12} color={mode.tintVar} className="mr-1" /> : null}
              </button>
            </li>
          );
        })}
      </ul>
    </Sheet>
  );
}
