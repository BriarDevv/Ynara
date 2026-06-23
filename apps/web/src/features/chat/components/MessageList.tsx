"use client";

import { useRef, useState } from "react";
import type { ModeId } from "@/components/ui/modes";
import type { ChatUiMessage } from "../store";
import { useChatAutoScroll } from "../useChatAutoScroll";
import { EmptyConversation } from "./EmptyConversation";
import { JumpToBottomButton } from "./JumpToBottomButton";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";

/**
 * Lista de mensajes de la conversación (a11y + auto-scroll inteligente, §10 / PR #9).
 *
 * a11y del streaming: la respuesta del assistant NO se anuncia token a token.
 * En vez de un `aria-live` sobre toda la lista (que spameaba al lector con cada
 * delta), una región `sr-only` dedicada (`<output>`, role="status" nativo +
 * aria-live="polite" aria-atomic) anuncia el texto final UNA sola vez, al cerrar en
 * "done". `aria-busy` sobre el scroller marca que el contenido se actualiza.
 * No se roba el foco al terminar (la región es pasiva, nadie llama `.focus()`).
 *
 * Auto-scroll inteligente (`useChatAutoScroll`): sigue pegado al fondo mientras
 * estés cerca del fondo; si scrolleás arriba, pausa y aparece el botón "ir al
 * final". Es scroll nativo sobre este scroller propio (`data-lenis-prevent`),
 * coordinado con Lenis (#7): Lenis maneja el `<main>` —inerte en chat—, no este.
 *
 * Typing indicator: se muestra cuando `isStreaming` es true y el último mensaje
 * del assistant todavía no tiene texto parcial (placeholder en "streaming" sin
 * texto = Ynara aún está procesando antes del primer token).
 */
type Props = {
  messages: ChatUiMessage[];
  mode: ModeId;
  /** Reintentar el último mensaje del usuario que falló. */
  onRetry: (messageId: string) => void;
  /** True mientras hay un stream SSE abierto (viene de `useChatStream`). */
  isStreaming?: boolean;
  /** Callback para enviar un prompt sugerido desde el estado vacío. */
  onSend?: (text: string) => void;
};

/** El último mensaje de assistant que cerró en "done" (o undefined). */
function lastDoneAssistant(messages: ChatUiMessage[]): ChatUiMessage | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m?.role === "assistant" && m.status === "done") return m;
  }
  return undefined;
}

/**
 * True si el assistant placeholder más reciente está en "streaming" pero
 * todavía no acumuló texto (= Ynara procesando antes del primer token).
 */
function isWaitingForFirstToken(messages: ChatUiMessage[]): boolean {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m?.role === "assistant") {
      return m.status === "streaming" && !m.text;
    }
  }
  return false;
}

export function MessageList({ messages, mode, onRetry, isStreaming = false, onSend }: Props) {
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

  const streamingFromStore = messages.some((m) => m.status === "streaming");
  // Combinamos el flag externo (hook) con el interno (store) para mayor robustez.
  const streaming = isStreaming || streamingFromStore;

  // Mostrar el typing indicator cuando hay stream activo y aún no hay texto parcial.
  const showTypingIndicator = isStreaming && isWaitingForFirstToken(messages);

  // Región viva dedicada: anuncia el texto del assistant UNA vez al cerrar en
  // "done". Al montar, adopta el historial ya presente sin anunciarlo (no
  // relee la última respuesta cada vez que abrís la conversación).
  //
  // Ajuste de estado DURANTE el render (patrón oficial de React para "adjusting
  // state when a prop changes"): comparamos el id del último "done" contra el
  // que ya anunciamos y, si cambió, seteamos el nuevo anuncio en el mismo render
  // (sin efecto → sin render extra con valor stale). El primer render adopta el
  // historial presente sin anunciarlo (`initialDoneId` capturado una vez).
  //
  // Re-anuncio de texto idéntico: el lector de pantalla no re-lee un nodo
  // `aria-atomic` cuyo string no cambió. En vez del viejo truco "" → rAF → text,
  // un `key` que incrementa con cada nuevo "done" REMONTA el `<output>`: nodo
  // nuevo ⇒ el lector lo anuncia aunque el texto sea igual al anterior. Sin
  // efecto, sin rAF, sin render intermedio con la UI stale.
  const [initialDoneId] = useState(() => lastDoneAssistant(messages)?.id ?? null);
  const [announced, setAnnounced] = useState<{ id: string | null; text: string; key: number }>({
    id: initialDoneId,
    text: "",
    key: 0,
  });
  const done = lastDoneAssistant(messages);
  if (done && done.id !== announced.id) {
    setAnnounced({ id: done.id, text: done.text, key: announced.key + 1 });
  }

  if (messages.length === 0) {
    return <EmptyConversation mode={mode} onSend={onSend ?? (() => {})} />;
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
        aria-busy={streaming}
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

        {/* Typing indicator: Ynara procesando antes del primer token */}
        {showTypingIndicator && <TypingIndicator modeId={mode} />}
      </div>

      {/* Región viva dedicada (visualmente oculta): el lector de pantalla
          anuncia acá la respuesta final, una sola vez, al cerrar el stream.
          `<output>` aporta role="status" nativo (semántica más confiable que
          role="status" manual); aria-live/atomic explícitos para garantizarlo. */}
      <output key={announced.key} className="sr-only" aria-live="polite" aria-atomic="true">
        {announced.text}
      </output>

      <JumpToBottomButton visible={showJumpButton} onClick={jumpToBottom} />
    </div>
  );
}
