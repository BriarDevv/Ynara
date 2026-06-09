import { type ChatRequest, type ChatResponse, ChatResponseSchema } from "@ynara/shared-schemas";
import { ApiError, api } from "./api";

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

/**
 * Extrae el código de error de un `ApiErrorBody` (`{ error: string, ... }`)
 * para mapearlo a copy humano vía `chatErrorCopy`. El backend real manda el
 * nombre de la clase `LlmError` en `error`; si no hay string ahí, devuelve
 * `undefined` y el copy cae al genérico.
 *
 * Compartido entre el path no-streaming (ChatScreen, recibe `ApiError`) y el
 * streaming (`useChatStream`, lee el body JSON del response no-ok), así el
 * mapeo no se duplica divergente.
 */
export function extractErrorCode(source: ApiError | unknown): string | undefined {
  const body = source instanceof ApiError ? source.body : source;
  if (body && typeof body === "object" && "error" in body) {
    const code = (body as { error: unknown }).error;
    if (typeof code === "string") return code;
  }
  return undefined;
}
