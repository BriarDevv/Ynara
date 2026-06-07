"use client";

import { useMutation } from "@tanstack/react-query";
import { LivingField } from "@/components/ui/LivingField";
import { ApiError } from "@/lib/api";
import { sendChatMessage } from "@/lib/chat";
import { useChatStore } from "../store";
import { ChatComposer } from "./ChatComposer";
import { ChatHeader } from "./ChatHeader";
import { MessageList } from "./MessageList";

/**
 * Pantalla de conversación (W2, no-streaming). Orquesta el flujo optimistic:
 * el mensaje del usuario aparece al instante, se llama `POST /v1/chat`, y al
 * volver la respuesta se cierra el ciclo (`applyChatResponse` marca el user
 * como "done" y agrega la respuesta del assistant en una transición atómica).
 *
 * El streaming (W3) reemplaza la mutation por `useChatStream`; la firma del
 * store ya lo contempla.
 */
export function ChatScreen({ sessionId }: { sessionId: string }) {
  const session = useChatStore((s) => s.sessions[sessionId]);
  const messages = useChatStore((s) => s.messages[sessionId]);
  const appendUserMessage = useChatStore((s) => s.appendUserMessage);
  const applyChatResponse = useChatStore((s) => s.applyChatResponse);
  const setMessageStatus = useChatStore((s) => s.setMessageStatus);

  // Un solo mensaje en vuelo a la vez: el composer queda `busy` mientras la
  // mutation corre, así no se puede disparar un segundo `mutate()` que
  // cancelaría los callbacks del primero (TanStack Query no encola). El envío
  // concurrente recién importa con streaming (W3), que usa otro mecanismo.
  const mutation = useMutation({
    mutationFn: ({ text }: { text: string; userMessageId: string }) =>
      sendChatMessage({ text, mode: session?.mode ?? "vida", session_id: sessionId }),
    onSuccess: (response, { userMessageId }) => {
      applyChatResponse(sessionId, userMessageId, response);
    },
    onError: (error, { userMessageId }) => {
      const code = error instanceof ApiError ? extractErrorCode(error) : undefined;
      setMessageStatus(sessionId, userMessageId, "error", code);
    },
  });

  // session puede ser undefined si el guard del dispatcher no corrió todavía;
  // el dispatcher (ChatRoute) garantiza que acá siempre haya sesión.
  if (!session) return null;

  const handleSend = (text: string) => {
    const userMessageId = appendUserMessage(sessionId, text);
    mutation.mutate({ text, userMessageId });
  };

  const handleRetry = (messageId: string) => {
    const msg = (messages ?? []).find((m) => m.id === messageId);
    if (!msg) return;
    setMessageStatus(sessionId, messageId, "sending");
    mutation.mutate({ text: msg.text, userMessageId: messageId });
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
        <MessageList messages={messages ?? []} mode={session.mode} onRetry={handleRetry} />
        <div className="px-4 pb-4">
          <ChatComposer onSend={handleSend} busy={mutation.isPending} />
        </div>
      </div>
    </div>
  );
}

/**
 * Extrae un código de error del `ApiErrorBody` para mapearlo a copy humano.
 * El backend real manda el nombre de la clase `LlmError` en `error`; si no
 * matchea, `chatErrorCopy` cae al genérico.
 */
function extractErrorCode(error: ApiError): string | undefined {
  const body = error.body;
  if (body && typeof body === "object" && "error" in body) {
    const code = (body as { error: unknown }).error;
    if (typeof code === "string") return code;
  }
  return undefined;
}
