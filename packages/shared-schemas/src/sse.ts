import {
  type StreamDone,
  StreamDoneSchema,
  type StreamError,
  StreamErrorSchema,
  type StreamToken,
  StreamTokenSchema,
} from "./chat";

/**
 * Parser de eventos SSE del chat — lógica pura, compartida web + mobile.
 *
 * El transporte (de dónde salen los bytes) difiere por plataforma: web usa
 * `fetch` + `ReadableStream`, mobile usa `expo/fetch`. Pero el *parsing* del
 * wire SSE con eventos con nombre (`event: token\ndata: {...}\n\n`) es
 * idéntico, así que vive acá y se testea contra el contrato del endpoint.
 *
 * Nota: los fixtures `.sse` de `apps/backend/tests/` son el wire *interno* del
 * cliente vLLM (chunks OpenAI sin `event:`), que este parser ignora a
 * propósito. El endpoint M9 los re-emite como los eventos con nombre de abajo,
 * que es lo que este parser consume.
 *
 * Contrato del stream (cerrado en #61, ver `RESPUESTAS-CONTRATO-CHAT.md`):
 *
 *   event: token
 *   data: {"delta": "Hola"}
 *
 *   event: done
 *   data: {"session_id": "...", "actions": [...], "finish_reason": "stop"}
 *
 *   event: error
 *   data: {"code": "...", "message": "..."}
 *
 * El parser NO sabe de `fetch`: recibe chunks de texto (`push`) y devuelve los
 * eventos completos que pudo cerrar en esa entrada, validados con Zod. Los
 * bloques incompletos quedan buffereados hasta el próximo `push`.
 */

/** Un evento del stream del chat, ya parseado y validado. */
export type ChatStreamEvent =
  | { type: "token"; data: StreamToken }
  | { type: "done"; data: StreamDone }
  | { type: "error"; data: StreamError };

/** Excepción de parseo: wire malformado o que no matchea el contrato. */
export class SseParseError extends Error {
  /** El bloque crudo que no se pudo parsear (sin datos de usuario garantido). */
  readonly raw: string;

  constructor(message: string, raw: string) {
    super(message);
    this.name = "SseParseError";
    this.raw = raw;
  }
}

type KnownEventName = "token" | "done" | "error";

function isKnownEvent(name: string): name is KnownEventName {
  return name === "token" || name === "done" || name === "error";
}

/**
 * Parsea un bloque SSE ya completo (sin el separador `\n\n`) a un evento.
 *
 * Devuelve `null` para bloques que se ignoran a propósito: comentarios SSE
 * (líneas que arrancan con `:`), heartbeats vacíos, o eventos sin nombre
 * conocido (p. ej. el `data: [DONE]` interno de vLLM, que el endpoint no
 * debería re-emitir pero toleramos por las dudas). Lanza `SseParseError` si
 * el bloque tiene un evento conocido pero su `data` está roto.
 */
function parseBlock(block: string): ChatStreamEvent | null {
  let eventName: string | null = null;
  const dataLines: string[] = [];

  for (const rawLine of block.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (line === "" || line.startsWith(":")) {
      continue; // comentario / línea en blanco
    }
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      // Por spec SSE el valor arranca tras "data:" + un espacio opcional.
      dataLines.push(line.slice("data:".length).replace(/^ /, ""));
    }
    // Otros campos SSE (id:, retry:) no aplican a este contrato; se ignoran.
  }

  if (eventName === null || !isKnownEvent(eventName)) {
    return null;
  }

  const dataText = dataLines.join("\n");
  if (dataText === "" || dataText === "[DONE]") {
    return null;
  }

  let json: unknown;
  try {
    json = JSON.parse(dataText);
  } catch {
    throw new SseParseError(`data no es JSON válido (event: ${eventName})`, block);
  }

  if (eventName === "token") {
    const parsed = StreamTokenSchema.safeParse(json);
    if (!parsed.success) {
      throw new SseParseError("data no matchea el contrato (event: token)", block);
    }
    return { type: "token", data: parsed.data };
  }

  if (eventName === "done") {
    const parsed = StreamDoneSchema.safeParse(json);
    if (!parsed.success) {
      throw new SseParseError("data no matchea el contrato (event: done)", block);
    }
    return { type: "done", data: parsed.data };
  }

  const parsed = StreamErrorSchema.safeParse(json);
  if (!parsed.success) {
    throw new SseParseError("data no matchea el contrato (event: error)", block);
  }
  return { type: "error", data: parsed.data };
}

/** Parser incremental con estado (buffer entre chunks). */
export interface SseParser {
  /** Alimenta un chunk de texto; devuelve los eventos completos que cerró. */
  push(chunk: string): ChatStreamEvent[];
  /** Cierra el stream; parsea cualquier bloque final sin `\n\n` de cierre. */
  flush(): ChatStreamEvent[];
}

/**
 * Crea un parser SSE incremental.
 *
 * Uso típico (transporte por plataforma alimenta `push`):
 *
 *   const parser = createSseParser();
 *   for await (const chunk of readChunks(response)) {
 *     for (const event of parser.push(chunk)) handle(event);
 *   }
 *   for (const event of parser.flush()) handle(event);
 */
export function createSseParser(): SseParser {
  let buffer = "";

  const drain = (final: boolean): ChatStreamEvent[] => {
    const events: ChatStreamEvent[] = [];
    // Normalizamos CRLF para separar bloques de forma uniforme.
    buffer = buffer.replace(/\r\n/g, "\n");

    let sepIndex = buffer.indexOf("\n\n");
    while (sepIndex !== -1) {
      const block = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      const event = parseBlock(block);
      if (event !== null) {
        events.push(event);
      }
      sepIndex = buffer.indexOf("\n\n");
    }

    if (final && buffer.trim() !== "") {
      const event = parseBlock(buffer);
      if (event !== null) {
        events.push(event);
      }
      buffer = "";
    }

    return events;
  };

  return {
    push(chunk: string): ChatStreamEvent[] {
      buffer += chunk;
      return drain(false);
    },
    flush(): ChatStreamEvent[] {
      return drain(true);
    },
  };
}

/**
 * Parsea un texto SSE completo de una (helper para tests y respuestas chicas).
 * Equivale a `push(text)` + `flush()`.
 */
export function parseSseText(text: string): ChatStreamEvent[] {
  const parser = createSseParser();
  return [...parser.push(text), ...parser.flush()];
}
