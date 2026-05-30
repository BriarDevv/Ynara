"use client";

import { CHAT_TEXT_MAX_LENGTH } from "@ynara/shared-schemas";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

/**
 * Composer del chat: textarea vivo (plan §4.2). Componente nuevo — NO toca el
 * `ChatInputDocked` de la home (eso es W5).
 *
 * - Enter envía; Shift+Enter inserta newline.
 * - Autosize hasta `MAX_ROWS` líneas, después scrollea.
 * - Vacío o solo-espacios → enviar deshabilitado.
 * - Límite ~4000 chars (`CHAT_TEXT_MAX_LENGTH`, mirror del backend M9). Se
 *   muestra un contador al acercarse y se bloquea el envío si se pasa.
 * - Mientras `busy` (esperando respuesta): textarea deshabilitado. El botón
 *   "Detener" (cancelar stream) llega en W3; acá `busy` solo deshabilita.
 * - Al enviar OK, se limpia y el foco vuelve al textarea (encadenar con teclado).
 */
type Props = {
  onSend: (text: string) => void;
  busy: boolean;
  /** Prefill desde una recomendación de la home (W5). */
  initialText?: string;
};

const MAX_ROWS = 8;
/** A cuántos chars del límite empezamos a mostrar el contador. */
const COUNTER_THRESHOLD = CHAT_TEXT_MAX_LENGTH - 300;

export function ChatComposer({ onSend, busy, initialText = "" }: Props) {
  const [text, setText] = useState(initialText);
  const ref = useRef<HTMLTextAreaElement>(null);

  // Autosize: ajustar la altura al contenido hasta MAX_ROWS.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const lineHeight = 24;
    const maxHeight = lineHeight * MAX_ROWS;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, []);

  const trimmed = text.trim();
  const tooLong = text.length > CHAT_TEXT_MAX_LENGTH;
  const canSend = trimmed.length > 0 && !tooLong && !busy;

  const handleSend = () => {
    if (!canSend) return;
    onSend(trimmed);
    setText("");
    // Devolver el foco para encadenar mensajes con teclado.
    requestAnimationFrame(() => ref.current?.focus());
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const showCounter = text.length >= COUNTER_THRESHOLD;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-end gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg)] p-2 focus-within:border-[var(--color-border-strong)]">
        <textarea
          ref={ref}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={busy}
          rows={1}
          aria-label="Escribí tu mensaje"
          placeholder="Escribí algo…"
          className="text-body max-h-[192px] flex-1 resize-none bg-transparent px-2 py-1.5 text-[var(--color-ink)] placeholder:text-[var(--color-ink-muted)] outline-none disabled:opacity-60"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Enviar"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-pill)] bg-gradient-blue-base text-[var(--color-on-dark)] transition-opacity duration-[var(--duration-base)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          →
        </button>
      </div>
      {showCounter ? (
        <p
          className={cn(
            "px-2 text-right text-caption",
            tooLong ? "text-[var(--color-error)]" : "text-[var(--color-ink-muted)]",
          )}
        >
          {text.length} / {CHAT_TEXT_MAX_LENGTH}
        </p>
      ) : null}
    </div>
  );
}
