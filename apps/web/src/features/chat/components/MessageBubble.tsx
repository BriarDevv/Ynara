"use client";

import { chatErrorCopy } from "@ynara/shared-schemas";
import { Button } from "@/components/ui/Button";
import { MODE_BY_ID, type ModeId } from "@/components/ui/modes";
import { cn } from "@/lib/cn";
import type { ChatUiMessage } from "../store";
import { Markdown } from "./Markdown";

/**
 * Una burbuja de la conversación.
 *
 * - Usuario: derecha, fondo ink suave, texto plano.
 * - Assistant: izquierda, hairline con el tint del modo, markdown sanitizado.
 * - Error: burbuja de sistema con copy humano (mapeado de `errorCode`) +
 *   botón reintentar (el handler lo pasa el padre).
 *
 * El cursor de streaming y el render token-a-token llegan en W3; acá el
 * status "streaming" se trata como texto parcial sin cursor.
 */
type Props = {
  message: ChatUiMessage;
  mode: ModeId;
  /** Reintentar el envío del mensaje del usuario que falló. */
  onRetry?: () => void;
};

export function MessageBubble({ message, mode, onRetry }: Props) {
  if (message.status === "error") {
    return (
      <div role="alert" className="flex flex-col items-start gap-2">
        <div className="max-w-[85%] rounded-[var(--radius-md)] border border-[var(--color-error)] bg-[var(--color-error-soft)] px-4 py-3">
          <p className="text-body text-[var(--color-ink)]">{chatErrorCopy(message.errorCode)}</p>
        </div>
        {onRetry ? (
          <Button variant="ghost" onClick={onRetry} className="px-3 py-1.5 text-body-sm">
            Reintentar
          </Button>
        ) : null}
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className={cn(
            "max-w-[85%] whitespace-pre-wrap rounded-[var(--radius-md)] bg-[var(--color-bg-soft)] px-4 py-3 text-body text-[var(--color-ink)]",
            message.status === "sending" && "opacity-70",
          )}
        >
          {message.text}
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[85%] gap-3">
        <span
          aria-hidden
          className="mt-1 w-0.5 shrink-0 self-stretch rounded-[var(--radius-pill)]"
          style={{ backgroundColor: MODE_BY_ID[mode].tintVar }}
        />
        <div className="text-body text-[var(--color-ink)]">
          <Markdown>{message.text}</Markdown>
        </div>
      </div>
    </div>
  );
}
