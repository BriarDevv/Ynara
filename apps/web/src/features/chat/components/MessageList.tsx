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
  // El último mensaje dispara el auto-scroll: su identidad cambia al llegar un
  // mensaje nuevo o al cambiar de status (objeto nuevo del store).
  const lastMessage = messages.at(-1);

  // Auto-scroll al fondo cuando llega contenido nuevo. El auto-scroll
  // inteligente (pausar si el user scrollea arriba + botón "↓ ir al final")
  // llega en W3, donde el texto crece token a token.
  useEffect(() => {
    if (!lastMessage) return;
    endRef.current?.scrollIntoView({ block: "end" });
  }, [lastMessage]);

  if (messages.length === 0) {
    return <EmptyConversation mode={mode} />;
  }

  return (
    // `data-lenis-prevent`: este es un scroller propio (la conversación), no el
    // del shell. El atributo evita que Lenis (§16 #7) capture el wheel/touch
    // acá, así la lista scrollea nativa y el `scrollIntoView` del auto-scroll no
    // pelea con Lenis. El no-encadenado al `<main>` lo da el `overscroll-behavior:
    // contain` que el stylesheet de Lenis aplica a `[data-lenis-prevent]`.
    <div
      className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4"
      aria-live="polite"
      data-lenis-prevent
    >
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
