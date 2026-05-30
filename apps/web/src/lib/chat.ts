import { type ChatRequest, type ChatResponse, ChatResponseSchema } from "@ynara/shared-schemas";
import { api } from "./api";

/**
 * Cliente del chat — caso **no-streaming** (`POST /v1/chat`).
 *
 * Usa el fetcher tipado `api.post` (que ya setea `Accept: application/json`).
 * El caso streaming (`POST /v1/chat/stream`) va en `useChatStream` con `fetch`
 * crudo + `ReadableStream` (W3), porque `api.ts` consume el body entero y no
 * sabe de streams — son rutas distintas a propósito (plan §5.2).
 *
 * La respuesta se valida con `ChatResponseSchema` (Pydantic gana, Zod sigue):
 * si el backend devuelve algo que no matchea el contrato, el parse tira y la
 * divergencia se detecta en vez de propagar datos mal formados a la UI.
 */
export async function sendChatMessage(req: ChatRequest): Promise<ChatResponse> {
  const raw = await api.post<unknown>("/v1/chat", req);
  return ChatResponseSchema.parse(raw);
}
