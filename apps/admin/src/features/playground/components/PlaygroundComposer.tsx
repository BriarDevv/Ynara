"use client";

import { Icon } from "@ynara/ui";
import { type KeyboardEvent, useEffect, useRef } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

/** Tope de caracteres del mensaje (= CHAT_TEXT_MAX_LENGTH del producto). */
const MAX_LENGTH = 4000;
/** A partir de cuántos caracteres restantes se muestra el contador. */
const COUNTER_THRESHOLD = 200;

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  /** Aborta el stream en curso (solo visible mientras `isStreaming`). */
  onStop: () => void;
  /** Deshabilita envío: serving fake, sin modelo o mensaje vacío. */
  canSend: boolean;
  /** True mientras hay un turno en vuelo (stream o agente): muestra "Detener". */
  isStreaming: boolean;
  className?: string;
};

/**
 * Compositor del chat, anclado al pie de la columna protagonista.
 *
 * Textarea autosize (crece con el contenido hasta un techo), Enter envía /
 * Shift+Enter inserta newline, `maxLength` 4000 con contador `tabular-nums` al
 * acercarse al tope. Acción dual según estado: "Enviar" (primary) cuando hay
 * espacio, "Detener" (con icono `detener`) mientras un turno está en vuelo.
 */
export function PlaygroundComposer({
  value,
  onChange,
  onSend,
  onStop,
  canSend,
  isStreaming,
  className,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Autosize: resetea el alto y lo ajusta al scrollHeight en cada cambio (techo
  // 200px). `value` es la dependencia real (el remeasure corre en cada cambio,
  // incluido el reset externo del padre tras enviar).
  // biome-ignore lint/correctness/useExhaustiveDependencies: `value` gatilla el remeasure (vía scrollHeight del ref, no por leerlo en el cuerpo).
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSend && !isStreaming) onSend();
    }
  };

  const remaining = MAX_LENGTH - value.length;
  const showCounter = remaining <= COUNTER_THRESHOLD;

  return (
    <div className={cn("flex items-end gap-3", className)}>
      <div className="flex flex-1 flex-col gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-3 focus-within:border-[var(--color-blue-flat)]">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={MAX_LENGTH}
          rows={1}
          placeholder="Escribí un mensaje para el modelo…"
          aria-label="Mensaje para el modelo"
          className="w-full resize-none bg-transparent text-body text-[var(--color-ink)] outline-none placeholder:text-[var(--color-ink-soft)]"
        />
        {showCounter ? (
          <span className="self-end text-caption tabular-nums text-[var(--color-ink-soft)]">
            {remaining}
          </span>
        ) : null}
      </div>

      {isStreaming ? (
        <Button variant="secondary" onClick={onStop} className="shrink-0">
          <Icon name="detener" size={16} />
          Detener
        </Button>
      ) : (
        <Button variant="primary" onClick={onSend} disabled={!canSend} className="shrink-0">
          <Icon name="enviar" size={16} />
          Enviar
        </Button>
      )}
    </div>
  );
}
