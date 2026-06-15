import { useMutation } from "@tanstack/react-query";
import { extractErrorCode, sendChatMessage } from "@ynara/core/features/chat";
import type { ChatRequest, Mode } from "@ynara/shared-schemas";
import { env } from "@/lib/env";
import { useChatStore } from "@/stores/chat";
import { mockChatResponse } from "./mockReply";

/**
 * Envío de un mensaje del chat (no-streaming, M1). Flujo optimistic: agrega el
 * mensaje del usuario al instante ("sending"), manda el turno y aplica la
 * respuesta o marca el mensaje como "error" (con copy + reintento).
 *
 * Fuente de la respuesta: mock canned local si `EXPO_PUBLIC_ENABLE_MOCKS`, si no
 * el `POST /v1/chat` real (autenticado con el token del user store). El streaming
 * llega en M2 (`/v1/chat/stream` con expo/fetch).
 */
export function useSendChat(sessionId: string, mode: Mode) {
  const appendUserMessage = useChatStore((s) => s.appendUserMessage);
  const applyChatResponse = useChatStore((s) => s.applyChatResponse);
  const setMessageStatus = useChatStore((s) => s.setMessageStatus);

  const mutation = useMutation({
    mutationFn: ({ text }: { text: string; userMessageId: string }) => {
      const req: ChatRequest = { text, mode, session_id: sessionId };
      return env.EXPO_PUBLIC_ENABLE_MOCKS ? mockChatResponse(req) : sendChatMessage(req);
    },
    onSuccess: (response, { userMessageId }) => {
      applyChatResponse(sessionId, userMessageId, response);
    },
    onError: (error, { userMessageId }) => {
      setMessageStatus(sessionId, userMessageId, "error", extractErrorCode(error));
    },
  });

  const send = (text: string) => {
    const userMessageId = appendUserMessage(sessionId, text);
    mutation.mutate({ text, userMessageId });
  };

  // Reintento del mensaje del usuario que falló: vuelve a "sending" y re-manda
  // el mismo turno conservando su id (no duplica la burbuja).
  const retry = (messageId: string, text: string) => {
    setMessageStatus(sessionId, messageId, "sending");
    mutation.mutate({ text, userMessageId: messageId });
  };

  return { send, retry, busy: mutation.isPending };
}
