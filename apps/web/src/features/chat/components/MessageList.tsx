"use client";

import { useEffect, useRef, useState } from "react";
import type { ModeId } from "@/components/ui/modes";
import type { ChatUiMessage } from "../store";
import { useChatAutoScroll } from "../useChatAutoScroll";
import { EmptyConversation } from "./EmptyConversation";
import { JumpToBottomButton } from "./JumpToBottomButton";
import { MessageBubble } from "./MessageBubble";

/**
 * Lista de mensajes de la conversación (a11y + auto-scroll inteligente, §10 / PR #9).
 *
 * a11y del streaming: la respuesta del assistant NO se anuncia token a token.
 * En vez de un `aria-live` sobre toda la lista (que spameaba al lector con cada
 * delta), una región `sr-only role="status" aria-live="polite" aria-atomic`
 * dedicada anuncia el texto final UNA sola vez, cuando el mensaje cierra en
 * "done". `aria-busy` sobre el scroller marca que el contenido se actualiza.
 * No se roba el foco al terminar (la región es pasiva, nadie llama `.focus()`).
 *
 * Auto-scroll inteligente (`useChatAutoScroll`): sigue pegado al fondo mientras
 * estés cerca del fondo; si scrolleás arriba, pausa y aparece el botón "ir al
 * final". Es scroll nativo sobre este scroller propio (`data-lenis-prevent`),
 * coordinado con Lenis (#7): Lenis maneja el `<main>` —inerte en chat—, no este.
 */
type Props = {
  messages: ChatUiMessage[];
  mode: ModeId;
  /** Reintentar el último mensaje del usuario que falló. */
  onRetry: (messageId: string) => void;
};

/** El último mensaje de assistant que cerró en "done" (o undefined). */
function lastDoneAssistant(messages: ChatUiMessage[]): ChatUiMessage | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m?.role === "assistant" && m.status === "done") return m;
  }
  return undefined;
}

export function MessageList({ messages, mode, onRetry }: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  // El contenido "crece" al llegar un mensaje nuevo o al sumar un token al
  // último (su texto se alarga). La key captura ambos: dispara el pin del
  // auto-scroll sin re-evaluar en cada render que no cambió el contenido.
  // Funciona porque `appendStreamDelta` SOLO appendea (la longitud crece
  // estrictamente); una edición in-place al mismo largo no dispararía el pin,
  // pero el store no hace eso. `text?.length` es defensivo ante un text ausente.
  const last = messages.at(-1);
  const growthKey = `${messages.length}:${last?.id ?? ""}:${last?.text?.length ?? 0}`;
  const { showJumpButton, jumpToBottom } = useChatAutoScroll(scrollerRef, growthKey);

  const isStreaming = messages.some((m) => m.status === "streaming");

  // Región viva dedicada: anuncia el texto del assistant UNA vez al cerrar en
  // "done". Al montar, adopta el historial ya presente sin anunciarlo (no
  // relee la última respuesta cada vez que abrís la conversación).
  const [announced, setAnnounced] = useState("");
  const announcedIdRef = useRef<string | null>(null);
  const initializedRef = useRef(false);
  const reannounceRaf = useRef(0);
  useEffect(() => {
    const done = lastDoneAssistant(messages);
    if (!initializedRef.current) {
      initializedRef.current = true;
      announcedIdRef.current = done?.id ?? null;
      return;
    }
    if (done && done.id !== announcedIdRef.current) {
      announcedIdRef.current = done.id;
      // Limpiar y re-setear en el próximo frame fuerza un cambio REAL del nodo
      // de texto aunque dos respuestas seguidas sean idénticas: React hace
      // bail-out si el string es igual y una región `aria-atomic` no re-anuncia
      // un valor reasignado igual. El "" intermedio es invisible (región sr-only).
      const { text } = done;
      setAnnounced("");
      if (reannounceRaf.current) cancelAnimationFrame(reannounceRaf.current);
      reannounceRaf.current = requestAnimationFrame(() => setAnnounced(text));
    }
  }, [messages]);
  // Cancela un re-anuncio pendiente al desmontar.
  useEffect(
    () => () => {
      if (reannounceRaf.current) cancelAnimationFrame(reannounceRaf.current);
    },
    [],
  );

  if (messages.length === 0) {
    return <EmptyConversation mode={mode} />;
  }

  return (
    // Wrapper `relative` para anclar el botón flotante "ir al final" al área de
    // mensajes (abajo-centro, arriba del composer). `min-h-0` deja que el
    // scroller interno haga overflow dentro del flex del shell.
    <div className="relative flex min-h-0 flex-1 flex-col">
      {/* `data-lenis-prevent`: este es un scroller propio (la conversación), no
          el del shell. Evita que Lenis (§16 #7) capture el wheel/touch acá; el
          no-encadenado al `<main>` lo da el `overscroll-behavior: contain` que
          el stylesheet de Lenis aplica a `[data-lenis-prevent]`. El auto-scroll
          (useChatAutoScroll) escribe `scrollTop` nativo sobre este elemento. */}
      <div
        ref={scrollerRef}
        // tabIndex=-1: focusable por programa (no entra en el orden de tab). Deja
        // que `jumpToBottom` pare el foco acá en vez de dejarlo caer a <body>
        // cuando el botón flotante se desmonta. `outline-none`: sin anillo por
        // ese foco programático (es la región scrolleable, no un control).
        tabIndex={-1}
        className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 outline-none"
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
      </div>

      {/* Región viva dedicada (visualmente oculta): el lector de pantalla
          anuncia acá la respuesta final, una sola vez, al cerrar el stream. */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announced}
      </div>

      <JumpToBottomButton visible={showJumpButton} onClick={jumpToBottom} />
    </div>
  );
}
