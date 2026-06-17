"use client";

import { CHAT_TEXT_MAX_LENGTH } from "@ynara/shared-schemas";
import { Icon } from "@ynara/ui";
import {
  type ChangeEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
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
  /** Modo de la sesión: tiñe el borde del composer y el botón de enviar. */
  mode: ModeId;
  /** Prefill desde una recomendación de la home (W5). */
  initialText?: string;
};

const MAX_ROWS = 8;
/** Alto de línea en px — debe matchear el line-height de `text-body`. */
const LINE_HEIGHT_PX = 24;
const MAX_HEIGHT_PX = LINE_HEIGHT_PX * MAX_ROWS;
/** A cuántos chars del límite empezamos a mostrar el contador. */
const COUNTER_THRESHOLD = CHAT_TEXT_MAX_LENGTH - 300;

export function ChatComposer({ onSend, busy, mode, initialText = "" }: Props) {
  const [text, setText] = useState(initialText);
  const ref = useRef<HTMLTextAreaElement>(null);
  const tintVar = MODE_BY_ID[mode].tintVar;

  // Autosize hasta MAX_ROWS; después scrollea internamente. Se corre en el
  // onChange (el textarea ya tiene el contenido nuevo, así que scrollHeight es
  // correcto y sin flicker) en vez de en un efecto — y una vez al montar para
  // el caso de `initialText` (prefill desde la home, W5).
  // `useCallback` con deps vacías: `resize` solo usa constantes de módulo, así
  // que es estable y el efecto de abajo corre una sola vez al montar (sizing
  // inicial para `initialText`) sin disparar el lint de deps exhaustivas.
  const resize = useCallback((el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, []);

  useEffect(() => {
    if (ref.current) resize(ref.current);
  }, [resize]);

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    resize(e.target);
  };

  const trimmed = text.trim();
  const tooLong = text.length > CHAT_TEXT_MAX_LENGTH;
  const canSend = trimmed.length > 0 && !tooLong && !busy;

  const handleSend = () => {
    if (!canSend) return;
    onSend(trimmed);
    setText("");
    // Devolver el foco y resetear la altura al limpiar.
    requestAnimationFrame(() => {
      const el = ref.current;
      if (!el) return;
      el.focus();
      resize(el);
    });
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
      {/* Composer glassmorphism (mockup): borde teñido por modo + blur + sombra.
          El bg semitransparente deja ver el campo vivo por detrás. */}
      <div
        className="flex items-end gap-2 rounded-[24px] border p-2 pl-3 shadow-soft backdrop-blur-[10px] transition-colors"
        style={{
          backgroundColor: "color-mix(in srgb, var(--color-bg) 72%, transparent)",
          borderColor: `color-mix(in srgb, ${tintVar} 22%, var(--color-border))`,
        }}
      >
        <textarea
          ref={ref}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={busy}
          rows={1}
          aria-label="Escribí tu mensaje"
          placeholder="Escribile a Ynara…"
          style={{ maxHeight: `${MAX_HEIGHT_PX}px` }}
          className="text-body flex-1 resize-none bg-transparent px-2 py-1.5 text-[var(--color-ink)] placeholder:text-[var(--color-ink-soft)] outline-none disabled:opacity-60"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Enviar"
          // Botón redondo teñido por el modo de la sesión (mockup); gris cuando
          // está deshabilitado (vacío o esperando respuesta).
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[var(--color-on-dark)] transition-[background-color,opacity] duration-[var(--duration-fast)] disabled:cursor-not-allowed disabled:opacity-50"
          style={{ backgroundColor: canSend ? tintVar : "var(--color-border-strong)" }}
        >
          <Icon name="enviar" size={18} />
        </button>
      </div>
      {showCounter ? (
        <p
          className={cn(
            "px-2 text-right text-caption",
            tooLong ? "text-[var(--color-error)]" : "text-[var(--color-ink-soft)]",
          )}
        >
          {text.length} / {CHAT_TEXT_MAX_LENGTH}
        </p>
      ) : null}
    </div>
  );
}
