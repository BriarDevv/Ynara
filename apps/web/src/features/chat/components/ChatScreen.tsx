"use client";

import { LivingField } from "@/components/ui/LivingField";
import { useChatStore } from "../store";
import { useChatStream } from "../useChatStream";
import { ChatComposer } from "./ChatComposer";
import { ChatHeader } from "./ChatHeader";
import { MessageList } from "./MessageList";

/**
 * Pantalla de conversación (W3, streaming). Orquesta el flujo optimistic:
 * el mensaje del usuario aparece al instante, `useChatStream` abre el SSE
 * `POST /v1/chat/stream` y el assistant crece token a token (el placeholder
 * en "streaming" se cierra como "done" al recibir el evento `done`).
 *
 * Reemplaza la `useMutation`/`sendChatMessage` del path no-streaming (W2);
 * el guard de "un solo mensaje en vuelo" lo provee ahora el hook.
 */
export function ChatScreen({ sessionId }: { sessionId: string }) {
  const session = useChatStore((s) => s.sessions[sessionId]);
  const messages = useChatStore((s) => s.messages[sessionId]);
  const appendUserMessage = useChatStore((s) => s.appendUserMessage);
  const setMessageStatus = useChatStore((s) => s.setMessageStatus);

  // Un solo stream en vuelo a la vez: el composer queda `busy` mientras
  // `isStreaming`, y el propio hook ignora un segundo `send()` concurrente.
  const stream = useChatStream(sessionId);

  // session puede ser undefined si el guard del dispatcher no corrió todavía;
  // el dispatcher (ChatRoute) garantiza que acá siempre haya sesión.
  if (!session) return null;

  const handleSend = (text: string) => {
    const userMessageId = appendUserMessage(sessionId, text);
    stream.send({ text, mode: session.mode, session_id: sessionId }, userMessageId);
  };

  const handleRetry = (messageId: string) => {
    // No-op si ya hay un stream en vuelo: `stream.send` lo ignoraría por el guard
    // single-in-flight, pero el mensaje ya quedaría marcado "sending" sin que nada
    // lo cierre (ni done ni error) → burbuja colgada. Gateamos antes de tocar el
    // status para evitar ese estado huérfano.
    if (stream.isStreaming) return;
    const msg = (messages ?? []).find((m) => m.id === messageId);
    if (!msg) return;
    setMessageStatus(sessionId, messageId, "sending");
    stream.send({ text: msg.text, mode: session.mode, session_id: sessionId }, messageId);
  };

  // `h-full`: calza exacto en el área de contenido del shell (que es de
  // altura fija con scroll interno); la `MessageList` scrollea adentro y el
  // composer queda anclado abajo, arriba de la tab bar. No declara `<main>`:
  // el landmark lo provee el AppShell. El wrapper exterior ancla el fondo
  // vivo a todo el ancho del área de contenido (no al max-w del hilo).
  return (
    <div className="relative isolate h-full">
      {/* Fondo vivo de Hablar (constellation, DESIGN.md §2.2), teñido por el
          modo de ESTA sesión — acá el modo preciso no es el global del
          onboarding sino el que el usuario eligió para la conversación. */}
      <LivingField variant="constellation" modeId={session.mode} />
      <div className="mx-auto flex h-full w-full max-w-[720px] flex-col">
        <ChatHeader mode={session.mode} />
        <MessageList
          messages={messages ?? []}
          mode={session.mode}
          onRetry={handleRetry}
          isStreaming={stream.isStreaming}
          onSend={handleSend}
        />
        <div className="px-4 pb-4">
          <ChatComposer
            onSend={handleSend}
            busy={stream.isStreaming}
            onStop={stream.cancel}
            mode={session.mode}
          />
        </div>
      </div>
    </div>
  );
}
