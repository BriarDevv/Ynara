"use client";

import { type ChatRequest, createSseParser, SseParseError } from "@ynara/shared-schemas";
import { useCallback, useEffect, useRef, useState } from "react";
import { applyAuthHeader } from "@/lib/api";
import { extractErrorCode } from "@/lib/chat";
import { env } from "@/lib/env";
import { useBackendSessionStore } from "./backendSessions";
import { useChatStore } from "./store";

/**
 * Hook de chat streaming (W3) — reemplaza la `useMutation`/`sendChatMessage`
 * no-streaming de ChatScreen por un stream token a token sobre SSE.
 *
 * Transporte: `fetch` crudo + `ReadableStream` (NO `api.post`, que consume el
 * body entero — plan §5.2). El parsing del wire SSE lo hace el parser puro
 * compartido (`createSseParser`, packages/shared-schemas), no se re-parsea acá.
 *
 * Ciclo de vida del mensaje (atómico en el store):
 *  - `startAssistantStream` ANTES del fetch: cierra el user optimista y crea
 *    el placeholder de assistant en "streaming". Se hace de entrada (no al
 *    primer token) para que el usuario vea la respuesta en curso de inmediato.
 *  - token → `appendStreamDelta`; done → `finishAssistantStream({actions})`;
 *    error (SSE o no-ok) → `failAssistantStream(code)`.
 *
 * Abort/cleanup: un `AbortController` por stream vive en un ref; `cancel()` lo
 * aborta (→ `cancelAssistantStream`, conserva el parcial) y el unmount aborta
 * también, matando fetch + reader sin leak (misma disciplina que el cleanup de
 * Lenis/rAF del repo). Un solo stream en vuelo a la vez (guard por ref).
 */

/** Headers del request de streaming, espejo de `lib/api.ts`. */
function buildStreamHeaders(url: string): Headers {
  const headers = new Headers({
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  });
  applyAuthHeader(headers, url);
  return headers;
}

export type UseChatStream = {
  /**
   * Abre un stream para `req`. `userMessageId` es el id del mensaje optimista
   * del usuario (de `appendUserMessage`) que se cierra al arrancar el stream.
   * No-op si ya hay un stream en vuelo.
   */
  send: (req: ChatRequest, userMessageId: string) => Promise<void>;
  /** Aborta el stream en curso (path "canceled"). No-op si no hay ninguno. */
  cancel: () => void;
  /** True mientras hay un stream abierto (para el `busy` del composer). */
  isStreaming: boolean;
};

export function useChatStream(sessionId: string): UseChatStream {
  const startAssistantStream = useChatStore((s) => s.startAssistantStream);
  const appendStreamDelta = useChatStore((s) => s.appendStreamDelta);
  const appendReasoningDelta = useChatStore((s) => s.appendReasoningDelta);
  const finishAssistantStream = useChatStore((s) => s.finishAssistantStream);
  const failAssistantStream = useChatStore((s) => s.failAssistantStream);
  const cancelAssistantStream = useChatStore((s) => s.cancelAssistantStream);
  const setBackendSessionId = useBackendSessionStore((s) => s.setBackendSessionId);

  const [isStreaming, setIsStreaming] = useState(false);
  // Stream en vuelo (null = no hay). Guarda el controller Y el id del assistant
  // destino, para que `cancel()`/unmount targeteen ESE mensaje por id (no por un
  // escaneo de status, que podría tocar un placeholder colgado de otro stream).
  // Vive en un ref para que el cleanup del unmount lo use sin re-render y para
  // servir de guard de "un solo stream a la vez".
  const inflightRef = useRef<{ controller: AbortController; assistantId: string } | null>(null);

  const send = useCallback(
    async (req: ChatRequest, userMessageId: string): Promise<void> => {
      // Guard: un solo stream en vuelo. Mismo criterio que el single-mutation
      // de la versión no-streaming. No hay `await` entre este check y el seteo
      // de `inflightRef.current` de abajo, así que el guard es un mutex sólido
      // en JS single-thread (dos `send()` sincrónicos no pueden pasar ambos).
      if (inflightRef.current) return;

      const controller = new AbortController();
      // Placeholder de assistant ANTES del fetch (affordance optimista). Todo
      // este tramo es sincrónico (no hay await hasta el fetch), así que el id
      // queda en el ref antes de cualquier punto de cancel.
      const assistantId = startAssistantStream(sessionId, userMessageId);
      inflightRef.current = { controller, assistantId };
      setIsStreaming(true);

      const url = `${env.NEXT_PUBLIC_API_URL}/v1/chat/stream`;
      const parser = createSseParser();
      // Hoisteado fuera del try para poder liberarlo en `finally` en cualquier
      // path de salida (incluido el happy path, que si no dejaría el body sin
      // drenar y el reader bloqueado en servidores keep-alive).
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;

      try {
        const response = await fetch(url, {
          method: "POST",
          headers: buildStreamHeaders(url),
          body: JSON.stringify(req),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          // Error del transporte: leemos el body (json si lo hay) y mapeamos
          // su `error` a un code igual que el path no-streaming.
          const body = await response.json().catch(() => null);
          failAssistantStream(sessionId, assistantId, extractErrorCode(body));
          return;
        }

        reader = response.body.getReader();
        const decoder = new TextDecoder();
        let failed = false;

        const handle = (events: ReturnType<typeof parser.push>): boolean => {
          // Devuelve true si hay que cortar (error o done).
          for (const event of events) {
            if (event.type === "token") {
              appendStreamDelta(sessionId, assistantId, event.data.delta);
            } else if (event.type === "reasoning") {
              // Razonamiento post-hoc (Camino A): llega ANTES de los token. Lo
              // acumulamos aparte (no toca el texto de la respuesta); la UI lo
              // muestra (o no) según el toggle display-only. No corta el stream.
              appendReasoningDelta(sessionId, assistantId, event.data.delta);
            } else if (event.type === "done") {
              // Adoptamos el `session_id` REAL que el backend resolvió/creó: en el
              // primer turno mandamos `null` y el backend devuelve acá el id de la
              // ChatSession nueva. Guardarlo (mapeo web-local localId→backendId) es
              // lo que permite encadenar los turnos siguientes; sin esto el 2do
              // turno volvería a crear sesión (memoria/historial fragmentados).
              setBackendSessionId(sessionId, event.data.session_id);
              // Pasamos `finish_reason` (antes se descartaba): si es "degraded"
              // (ADR-027, IA no disponible) el store marca el turno degradado y
              // la UI muestra un estado honesto en vez de la respuesta enlatada.
              finishAssistantStream(sessionId, assistantId, {
                actions: event.data.actions,
                finishReason: event.data.finish_reason,
              });
              return true;
            } else {
              failAssistantStream(sessionId, assistantId, event.data.code);
              failed = true;
              return true;
            }
          }
          return false;
        };

        let stopped = false;
        while (!stopped) {
          // El read es secuencial por diseño: cada `await reader.read()` devuelve
          // el SIGUIENTE chunk del MISMO stream SSE (depende del cursor del read
          // anterior). No son llamadas independientes; no se pueden paralelizar.
          // react-doctor-disable-next-line react-doctor/async-await-in-loop
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          stopped = handle(parser.push(chunk));
        }
        // Flush del decoder: si el stream cortó en medio de un codepoint
        // multibyte (truncado/abortado), esos bytes quedaron en el buffer
        // interno del decoder. Sin este flush final se perderían (relevante
        // para acentos/emojis del producto en español).
        if (!stopped) {
          const tail = decoder.decode();
          if (tail) stopped = handle(parser.push(tail));
        }
        // Bloque final sin `\n\n` de cierre (p. ej. el done pegado al EOF).
        if (!stopped) {
          handle(parser.flush());
        }
        // Si el loop terminó (EOF) sin done ni error explícito, el placeholder
        // queda en "streaming"; lo cerramos para no dejarlo colgado.
        if (!failed) {
          const last = useChatStore
            .getState()
            .messages[sessionId]?.find((m) => m.id === assistantId);
          if (last?.status === "streaming") {
            finishAssistantStream(sessionId, assistantId);
          }
        }
      } catch (error) {
        // AbortError = path de cancel: ya lo maneja `cancel()` vía
        // cancelAssistantStream, lo tragamos.
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        // SseParseError u otro fallo del transporte: cerramos en error.
        const code = error instanceof SseParseError ? "stream_parse_error" : undefined;
        failAssistantStream(sessionId, assistantId, code);
      } finally {
        // Teardown en TODOS los paths de salida (incluido el happy path tras el
        // `done`): cancelamos el reader para liberar el body y devolver la
        // conexión al pool —si no, un servidor keep-alive deja el reader
        // bloqueado y la conexión colgada. El abort es idempotente y no-op una
        // vez que el stream terminó.
        try {
          await reader?.cancel();
        } catch {
          // El reader ya pudo estar liberado/errored; liberar es best-effort.
        }
        controller.abort();
        inflightRef.current = null;
        setIsStreaming(false);
      }
    },
    [
      sessionId,
      startAssistantStream,
      appendStreamDelta,
      appendReasoningDelta,
      finishAssistantStream,
      failAssistantStream,
      setBackendSessionId,
    ],
  );

  const cancel = useCallback(() => {
    const inflight = inflightRef.current;
    if (!inflight) return;
    // Marcamos canceled ANTES de abortar: el abort dispara el catch (AbortError)
    // que lo traga, así el status "canceled" no se pisa. Targeteamos el assistant
    // exacto de ESTE stream por id (no por escaneo de status), para no tocar un
    // placeholder colgado de un stream anterior de la misma sesión.
    cancelAssistantStream(sessionId, inflight.assistantId);
    inflight.controller.abort();
  }, [sessionId, cancelAssistantStream]);

  // Cleanup: al desmontar (navegar fuera) con un stream en vuelo, lo cancelamos
  // —marca el assistant "canceled" (status verídico: el stream se cortó porque
  // el usuario se fue) y aborta fetch + reader. Targetear por id (vía `cancel`)
  // hace esto seguro; antes solo abortábamos y dejábamos el mensaje colgado en
  // "streaming", que reaparecía como un bubble con spinner que nunca cerraba.
  // Un `cancel` recreado no debe re-disparar el effect, así que lo leemos de un
  // ref que siempre apunta al último.
  const cancelRef = useRef(cancel);
  cancelRef.current = cancel;
  // Deps `[]` a propósito: el effect solo debe correr al montar/desmontar. El
  // cleanup lee `cancelRef.current` (latest-ref pattern), que SIEMPRE apunta al
  // último `cancel`, así que no hay nodo stale; agregar `cancel` a deps re-correría
  // el cleanup en cada render y cancelaría el stream en vuelo por error.
  // react-doctor-disable-next-line react-doctor/exhaustive-deps
  useEffect(() => {
    return () => {
      cancelRef.current();
    };
  }, []);

  return { send, cancel, isStreaming };
}
