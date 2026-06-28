"use client";

import { useShowReasoningStore } from "@/stores/showReasoning";

/**
 * Switch accesible "Ver razonamiento" (display-only). Prende/apaga el colapsable
 * "Pensando…" de las respuestas; NO manda nada al backend ni cambia el thinking
 * del modelo. Vive en la toolbar del composer del chat.
 *
 * a11y: `role="switch"` + `aria-checked` ligado al store. El track/thumb es
 * decorativo (`aria-hidden`); el estado lo comunica el role + el label visible.
 */
export function ReasoningToggle() {
  const enabled = useShowReasoningStore((s) => s.enabled);
  const toggle = useShowReasoningStore((s) => s.toggle);

  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      onClick={toggle}
      data-testid="toggle-reasoning"
      className="inline-flex items-center gap-2 rounded-[var(--radius-pill)] px-2 py-1 text-caption text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
    >
      <span
        aria-hidden
        className="relative inline-flex h-4 w-7 shrink-0 items-center rounded-[var(--radius-pill)] transition-colors duration-[var(--duration-fast)] motion-reduce:transition-none"
        style={{
          backgroundColor: enabled ? "var(--color-ink)" : "var(--color-border-strong)",
        }}
      >
        <span
          className="absolute h-3 w-3 rounded-[var(--radius-pill)] bg-[var(--color-bg)] transition-transform duration-[var(--duration-fast)] motion-reduce:transition-none"
          style={{ transform: enabled ? "translateX(13px)" : "translateX(3px)" }}
        />
      </span>
      <span>Ver razonamiento</span>
    </button>
  );
}
