import { cannedActions, cannedReply } from "@ynara/core/features/chat";
import type { ChatRequest, ChatResponse } from "@ynara/shared-schemas";

/**
 * Respuesta canned LOCAL del chat (mock-first, `EXPO_PUBLIC_ENABLE_MOCKS`) — sin
 * LLM. Reusa el copy por modo de @ynara/core (`cannedReply`/`cannedActions`) y
 * simula una latencia corta para que la UI muestre el estado "enviando". Cuando
 * exista el serving de IA del equipo, se apaga el flag y se pega al
 * `POST /v1/chat` real (`sendChatMessage`).
 */
export function mockChatResponse(req: ChatRequest): Promise<ChatResponse> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        text: cannedReply(req.mode, req.text),
        actions: cannedActions(req.mode),
        session_id: req.session_id ?? "mock-session",
        finish_reason: "stop",
      });
    }, 500);
  });
}
