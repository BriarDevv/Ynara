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
  onClear: () => void;
  /** Deshabilita envío: serving fake, sin modelo, mensaje vacío o turno en vuelo. */
  canSend: boolean;
  /** True mientras la mutation está en vuelo (bloquea el textarea y el envío). */
  isPending: boolean;
  className?: string;
};

/**
 * Banda 3 del Playground (ADR-018 §3): el compositor, anclado abajo.
 *
 * Textarea autosize (crece con el contenido hasta un techo), Enter envía /
 * Shift+Enter inserta newline, `maxLength` 4000 con contador `tabular-nums` que
 * aparece al acercarse al tope. Acción dual: "Enviar" (primary, icono `enviar`)
 * + "Limpiar" (ghost). El envío se deshabilita por `canSend` (serving fake / sin
 * modelo / mensaje vacío) o mientras `isPending`.
 */
export function PlaygroundComposer({
  value,
  onChange,
  onSend,
  onClear,
  canSend,
  isPending,
  className,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Autosize: resetea el alto y lo ajusta al scrollHeight en cada cambio (techo
  // 240px). `value` es la dependencia REAL del efecto aunque no se lea en el
  // cuerpo: el remeasure debe correr en cada cambio de texto, incluido cuando el
  // padre lo resetea externamente (handleSend/handleClear ponen el draft en "").
  // biome-ignore lint/correctness/useExhaustiveDependencies: `value` gatilla el remeasure (su efecto es vía scrollHeight del ref, no por leerlo en el cuerpo).
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [value]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSend && !isPending) onSend();
    }
  };

  const remaining = MAX_LENGTH - value.length;
  const showCounter = remaining <= COUNTER_THRESHOLD;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-col gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg)] p-3 focus-within:border-[var(--color-blue-flat)]">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={MAX_LENGTH}
          disabled={isPending}
          rows={2}
          placeholder="Escribí un mensaje para el modelo…"
          aria-label="Mensaje para el modelo"
          className="w-full resize-none bg-transparent text-body text-[var(--color-ink)] outline-none placeholder:text-[var(--color-ink-soft)] disabled:cursor-not-allowed disabled:opacity-50"
        />
        {showCounter ? (
          <span className="self-end text-caption tabular-nums text-[var(--color-ink-soft)]">
            {remaining}
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        <Button variant="primary" onClick={onSend} disabled={!canSend || isPending}>
          <Icon name="enviar" size={16} />
          Enviar
        </Button>
        <Button variant="ghost" onClick={onClear} disabled={isPending || value.length === 0}>
          Limpiar
        </Button>
      </div>
    </div>
  );
}
