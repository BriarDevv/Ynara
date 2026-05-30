"use client";

import { useEffect, useRef } from "react";
import type { ModeId } from "@/components/ui/modes";
import type { ChatUiMessage } from "../store";
import { EmptyConversation } from "./EmptyConversation";
import { MessageBubble } from "./MessageBubble";

/**
 * Lista de mensajes de la conversación.
 *
 * Auto-scroll básico al fondo cuando llega contenido nuevo (W2). El
 * auto-scroll inteligente — pausar si el usuario scrollea arriba + botón
 * "↓ Ir al final" — llega en W3 junto al streaming, donde el texto crece
 * token a token y la UX se vuelve crítica.
 *
 * `aria-live="polite"` para que el lector de pantalla anuncie la respuesta
 * del assistant sin interrumpir; se refina en W3 (streaming).
 */
type Props = {
  messages: ChatUiMessage[];
  mode: ModeId;
  /** Reintentar el último mensaje del usuario que falló. */
  onRetry: (messageId: string) => void;
};

export function MessageList({ messages, mode, onRetry }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, []);

  if (messages.length === 0) {
    return <EmptyConversation mode={mode} />;
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto py-4" aria-live="polite">
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          message={message}
          mode={mode}
          onRetry={
            message.status === "error" && message.role === "user"
              ? () => onRetry(message.id)
              : undefined
          }
        />
      ))}
      <div ref={endRef} />
    </div>
  );
}
