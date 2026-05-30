/**
 * Copy de usuario del chat: compartido web + mobile para no divergir.
 *
 * El mapeo error a copy humano espeja la taxonomia de
 * apps/backend/app/llm/errors.py (ver tabla en el plan, seccion 2.5). Los
 * errores marcados "interno" caen al generico para no exponer detalle de
 * infra/tools/memoria al usuario. Todo el texto de usuario vive aca para
 * facilitar i18n futuro.
 */

/** Copy generico cuando el codigo de error es interno o desconocido. */
export const CHAT_ERROR_FALLBACK = "Algo falló de mi lado. Probá de nuevo.";

/**
 * Codigos de error user-facing mapeados a copy rioplatense.
 *
 * Las claves son los nombres de las clases LlmError del backend. El endpoint
 * mapea cada excepcion a un code en el ApiErrorBody / evento error; este
 * objeto traduce ese code a texto. Los errores internos (ModelNotServedError,
 * ToolParsingError, MemoryRetrievalError) no estan aca a proposito: caen al
 * fallback.
 */
export const CHAT_ERROR_COPY: Record<string, string> = {
  LlmTimeoutError: "Me colgué un segundo, ¿lo reintentás?",
  LlmUnavailableError: "No te puedo responder ahora mismo. Probá en un rato.",
  LlmOverloadedError: "Estoy saturado, dame un momento y reintentá.",
  LlmBadRequestError: "No pude procesar eso. ¿Lo reformulás?",
  LlmContextOverflowError: "Esta charla se hizo muy larga. Arrancá una nueva.",
  ToolExecutionError: "No pude completar esa acción.",
};

/**
 * Devuelve el copy humano para un codigo de error del chat.
 * Cae al generico si el codigo es interno o desconocido.
 */
export function chatErrorCopy(code: string | null | undefined): string {
  if (!code) {
    return CHAT_ERROR_FALLBACK;
  }
  return CHAT_ERROR_COPY[code] ?? CHAT_ERROR_FALLBACK;
}
