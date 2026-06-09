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
 * "↓ Ir al final" — llega en PR #9: el streaming (W3) hace crecer el texto
 * token a token y ahí esa UX se vuelve crítica, pero el refinamiento va aparte.
 *
 * `aria-live="polite"` para que el lector de pantalla anuncie la respuesta
 * del assistant sin interrumpir. Como el streaming muta el texto token a token,
 * W3 agrega `aria-busy` mientras hay un mensaje creciendo, para que el lector no
 * lea cada fragmento parcial; el refinamiento completo (región de status
 * dedicada que anuncia solo al cerrar + auto-scroll inteligente) es PR #9.
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
  // Mientras un mensaje crece token a token, `aria-busy` le avisa al lector de
  // pantalla que la región se está actualizando, para que aguante el anuncio en
  // vez de leer cada fragmento parcial (guard mínimo de a11y; refinamiento en #9).
  const isStreaming = messages.some((m) => m.status === "streaming");

  // Auto-scroll al fondo cuando llega contenido nuevo. El auto-scroll
  // inteligente (pausar si el user scrollea arriba + botón "↓ ir al final")
  // llega en PR #9; este PR (W3) trae el streaming pero no ese refinamiento.
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
      aria-busy={isStreaming}
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
