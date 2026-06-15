import { type ChatRequest, type ChatResponse, ChatResponseSchema } from "@ynara/shared-schemas";
import { ApiError, api } from "../../api";

/*
 * Cliente del chat — caso no-streaming (`POST /v1/chat`), compartido web +
 * mobile (ADR-012). El streaming (`POST /v1/chat/stream`) va aparte con
 * `expo/fetch`/`fetch` + ReadableStream (M2), porque el cliente HTTP consume el
 * body entero y no sabe de streams.
 *
 * La respuesta se valida con `ChatResponseSchema` (Pydantic gana, Zod sigue):
 * si el backend devuelve algo fuera de contrato, el parse tira y la divergencia
 * se detecta en vez de propagarse a la UI.
 */
export async function sendChatMessage(req: ChatRequest): Promise<ChatResponse> {
  const raw = await api.post<unknown>("/v1/chat", req);
  return ChatResponseSchema.parse(raw);
}

/**
 * Extrae el código de error del `ApiErrorBody` (`{ error: string, ... }`) para
 * mapearlo a copy humano con `chatErrorCopy`. El backend manda el nombre de la
 * clase `LlmError` en `error`; sin string ahí devuelve `undefined` (cae al
 * genérico).
 */
export function extractErrorCode(source: ApiError | unknown): string | undefined {
  const body = source instanceof ApiError ? source.body : source;
  if (body && typeof body === "object" && "error" in body) {
    const code = (body as { error: unknown }).error;
    if (typeof code === "string") return code;
  }
  return undefined;
}
