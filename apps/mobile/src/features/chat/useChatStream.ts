import { applyAuthHeader, getBaseUrl } from "@ynara/core/api";
import { cannedActions, cannedReply, extractErrorCode } from "@ynara/core/features/chat";
import { type ChatRequest, createSseParser, SseParseError } from "@ynara/shared-schemas";
import { fetch as expoFetch } from "expo/fetch";
import { useCallback, useEffect, useRef, useState } from "react";
import { env } from "@/lib/env";
import { useChatStore } from "@/stores/chat";

/**
 * Hook de chat streaming (M2, mobile) — reemplaza el envío no-streaming de M1
 * por un stream token a token. Espejo del `useChatStream` de web, con dos
 * diferencias de plataforma:
 *
 * - Transporte: `expo/fetch` (WinterCG, expone `response.body` como
 *   ReadableStream; el `fetch` global de RN devuelve el body entero). El parsing
 *   del wire SSE lo hace el parser puro compartido (`createSseParser`).
 * - Mock-first: con `EXPO_PUBLIC_ENABLE_MOCKS` emite la respuesta canned por modo
 *   (de @ynara/core) troceada con delays — el mismo efecto token-a-token sin LLM.
 *   Con el flag en false pega al `POST /v1/chat/stream` real (autenticado).
 *
 * Ciclo de vida (atómico en el store): `startAssistantStream` ANTES de arrancar
 * (cierra el user optimista + crea el placeholder "streaming"); token →
 * `appendStreamDelta`; done → `finishAssistantStream({actions})`; error →
 * `failAssistantStream(code)`; cancel/unmount → `cancelAssistantStream` (conserva
 * el parcial). Un solo stream en vuelo (guard por ref).
 */

export type UseChatStream = {
  send: (req: ChatRequest, userMessageId: string) => Promise<void>;
  cancel: () => void;
  isStreaming: boolean;
};

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function useChatStream(sessionId: string): UseChatStream {
  const startAssistantStream = useChatStore((s) => s.startAssistantStream);
  const appendStreamDelta = useChatStore((s) => s.appendStreamDelta);
  const finishAssistantStream = useChatStore((s) => s.finishAssistantStream);
  const failAssistantStream = useChatStore((s) => s.failAssistantStream);
  const cancelAssistantStream = useChatStore((s) => s.cancelAssistantStream);

  const [isStreaming, setIsStreaming] = useState(false);
  const inflightRef = useRef<{ controller: AbortController; assistantId: string } | null>(null);

  const send = useCallback(
    async (req: ChatRequest, userMessageId: string): Promise<void> => {
      // Guard: un solo stream en vuelo (mutex sólido en JS single-thread, no hay
      // await entre el check y el seteo del ref).
      if (inflightRef.current) return;

      const controller = new AbortController();
      const assistantId = startAssistantStream(sessionId, userMessageId);
      inflightRef.current = { controller, assistantId };
      setIsStreaming(true);

      try {
        if (env.EXPO_PUBLIC_ENABLE_MOCKS) {
          // Mock: trocea la respuesta canned por modo en palabras y las emite con
          // delays. El cancel() ya marcó "canceled", así que al ver aborted solo
          // cortamos (no re-tocamos el store).
          const full = cannedReply(req.mode, req.text);
          const tokens = full.match(/\S+\s*/g) ?? [full];
          for (const token of tokens) {
            await delay(45);
            if (controller.signal.aborted) return;
            appendStreamDelta(sessionId, assistantId, token);
          }
          finishAssistantStream(sessionId, assistantId, { actions: cannedActions(req.mode) });
          return;
        }

        // Real: POST /v1/chat/stream con expo/fetch + parser SSE compartido.
        const url = `${getBaseUrl()}/v1/chat/stream`;
        const headers = new Headers({
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        });
        applyAuthHeader(headers, url);
        const parser = createSseParser();
        let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;

        try {
          const response = await expoFetch(url, {
            method: "POST",
            headers,
            body: JSON.stringify(req),
            signal: controller.signal,
          });

          if (!response.ok || !response.body) {
            const body = await response.json().catch(() => null);
            failAssistantStream(sessionId, assistantId, extractErrorCode(body));
            return;
          }

          reader = response.body.getReader();
          const decoder = new TextDecoder();
          let failed = false;

          // Devuelve true si hay que cortar (done o error).
          const handle = (events: ReturnType<typeof parser.push>): boolean => {
            for (const event of events) {
              if (event.type === "token") {
                appendStreamDelta(sessionId, assistantId, event.data.delta);
              } else if (event.type === "done") {
                finishAssistantStream(sessionId, assistantId, { actions: event.data.actions });
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
            const { done, value } = await reader.read();
            if (done) break;
            stopped = handle(parser.push(decoder.decode(value, { stream: true })));
          }
          // Flush de bytes multibyte truncados (acentos/emojis) + bloque final.
          if (!stopped) {
            const tail = decoder.decode();
            if (tail) stopped = handle(parser.push(tail));
          }
          if (!stopped) handle(parser.flush());
          // EOF sin done explícito: cerramos el placeholder colgado.
          if (!failed) {
            const last = useChatStore
              .getState()
              .messages[sessionId]?.find((m) => m.id === assistantId);
            if (last?.status === "streaming") finishAssistantStream(sessionId, assistantId);
          }
        } finally {
          try {
            await reader?.cancel();
          } catch {
            // best-effort: el reader ya pudo estar liberado.
          }
        }
      } catch (error) {
        // AbortError = path de cancel (ya lo marcó cancel()); lo tragamos.
        if (error instanceof Error && error.name === "AbortError") return;
        const code = error instanceof SseParseError ? "stream_parse_error" : undefined;
        failAssistantStream(sessionId, assistantId, code);
      } finally {
        controller.abort();
        inflightRef.current = null;
        setIsStreaming(false);
      }
    },
    [
      sessionId,
      startAssistantStream,
      appendStreamDelta,
      finishAssistantStream,
      failAssistantStream,
    ],
  );

  const cancel = useCallback(() => {
    const inflight = inflightRef.current;
    if (!inflight) return;
    // Marcar "canceled" ANTES de abortar (el abort dispara el catch que lo traga),
    // targeteando el assistant exacto de este stream por id.
    cancelAssistantStream(sessionId, inflight.assistantId);
    inflight.controller.abort();
  }, [sessionId, cancelAssistantStream]);

  // Cancelar el stream en vuelo al desmontar (navegar fuera). Un cancel recreado
  // no debe re-disparar el effect: lo leemos de un ref que apunta al último.
  const cancelRef = useRef(cancel);
  cancelRef.current = cancel;
  useEffect(() => {
    return () => cancelRef.current();
  }, []);

  return { send, cancel, isStreaming };
}
