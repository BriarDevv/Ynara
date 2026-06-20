"use client";

import { useCallback, useRef, useState } from "react";
import { env } from "@/lib/env";
import { useAdminStore } from "@/stores/admin";
import { splitThinkingLive } from "../lib/thinking";
import {
  type PlaygroundInT,
  PlaygroundStreamDone,
  type PlaygroundStreamDoneT,
  PlaygroundStreamError,
  PlaygroundStreamReasoning,
  PlaygroundStreamToken,
} from "../schemas";

/**
 * Hook de streaming SSE del Playground (`POST /v1/admin/playground/stream`).
 *
 * A diferencia del probe sync (`usePlayground`), el transporte es
 * `text/event-stream`: abrimos un `fetch` con el Bearer admin, leemos el body
 * por chunks y parseamos los frames SSE (`event:`/`data:`). Cada `data` se valida
 * con su Zod en el borde (igual que el resto del panel). El hook dueña el "turno
 * en vuelo" (texto + thinking + métricas en vivo) y avisa por callbacks cuando
 * termina (`onComplete`) o falla (`onError`) para que el caller lo persista.
 *
 * Tokens/seg en vivo: `completion_tokens` acumulados / segundos transcurridos
 * desde el primer byte, recalculado en cada token. El server manda además el
 * agregado final en `done` (autoritativo).
 */

/** Fase del turno en vuelo. */
export type StreamPhase = "idle" | "streaming" | "done" | "error";

/** Estado observable del turno en vuelo (lo renderiza el thread del chat). */
export type LiveTurn = {
  phase: StreamPhase;
  /** Texto crudo acumulado (incluye `<think>` si el modelo lo emitió). */
  rawText: string;
  /** Texto de respuesta limpio (sin el bloque de razonamiento), en vivo. */
  text: string;
  /** Razonamiento en curso separado del texto (qwen thinking), o `null`. */
  thinking: string | null;
  /** Tokens de completion contados (chunks con delta no vacío). */
  completionTokens: number;
  /** Tokens por segundo en vivo. */
  tokensPerSecond: number;
  /** Status HTTP del error (para mapear copy neutro), o `null`. */
  errorStatus: number | null;
};

const IDLE: LiveTurn = {
  phase: "idle",
  rawText: "",
  text: "",
  thinking: null,
  completionTokens: 0,
  tokensPerSecond: 0,
  errorStatus: null,
};

/** El turno finalizado que se persiste en la sesión. */
export type StreamFinal = {
  text: string;
  thinking: string | null;
  done: PlaygroundStreamDoneT;
};

type StartCallbacks = {
  onComplete: (final: StreamFinal) => void;
  onError: (status: number | null) => void;
};

/** Parsea un frame SSE (`event: X\ndata: Y`) a `{ event, data }`. */
function parseFrame(frame: string): { event: string; data: string } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

export function usePlaygroundStream() {
  const [live, setLive] = useState<LiveTurn>(IDLE);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLive(IDLE);
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLive((prev) => (prev.phase === "streaming" ? IDLE : prev));
  }, []);

  const start = useCallback(
    async (input: PlaygroundInT, { onComplete, onError }: StartCallbacks) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const startedAt = performance.now();
      let raw = "";
      let reasoning = "";
      let tokens = 0;
      setLive({ ...IDLE, phase: "streaming" });

      const apply = () => {
        const split = splitThinkingLive(raw);
        const elapsed = (performance.now() - startedAt) / 1000;
        const tps = elapsed > 0 ? tokens / elapsed : 0;
        setLive({
          phase: "streaming",
          rawText: raw,
          text: split.text,
          // El canal `reasoning` separado (qwen) tiene precedencia; si no, el bloque
          // `<think>` embebido que `splitThinkingLive` haya separado del texto.
          thinking: reasoning || split.thinking,
          completionTokens: tokens,
          tokensPerSecond: tps,
          errorStatus: null,
        });
      };

      const fail = (status: number | null) => {
        setLive({ ...IDLE, phase: "error", errorStatus: status });
        onError(status);
      };

      try {
        const token = useAdminStore.getState().token;
        const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/v1/admin/playground/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            Accept: "text/event-stream",
          },
          body: JSON.stringify(input),
          signal: controller.signal,
        });

        // Errores de validación/gate (422/409/401/…) llegan como JSON, no SSE.
        if (!res.ok || !res.body) {
          fail(res.status);
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // Frames separados por línea en blanco (`\n\n`).
          let sep = buffer.indexOf("\n\n");
          while (sep !== -1) {
            const frame = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            const parsed = parseFrame(frame);
            if (parsed) {
              if (parsed.event === "token") {
                const t = PlaygroundStreamToken.safeParse(safeJson(parsed.data));
                if (t.success) {
                  raw += t.data.delta;
                  tokens += 1;
                  apply();
                }
              } else if (parsed.event === "reasoning") {
                const r = PlaygroundStreamReasoning.safeParse(safeJson(parsed.data));
                if (r.success) {
                  reasoning += r.data.delta;
                  apply();
                }
              } else if (parsed.event === "done") {
                const d = PlaygroundStreamDone.safeParse(safeJson(parsed.data));
                if (d.success) {
                  const split = splitThinkingLive(raw);
                  setLive(IDLE);
                  abortRef.current = null;
                  onComplete({
                    text: split.text,
                    // Precedencia: el `thinking` autoritativo del server > el canal
                    // `reasoning` acumulado en vivo > el `<think>` embebido.
                    thinking: d.data.thinking ?? (reasoning || split.thinking),
                    done: d.data,
                  });
                  return;
                }
              } else if (parsed.event === "error") {
                PlaygroundStreamError.safeParse(safeJson(parsed.data));
                fail(null);
                return;
              }
            }
            sep = buffer.indexOf("\n\n");
          }
        }
        // El stream cerró sin `done`: lo tratamos como fallo de transporte.
        fail(null);
      } catch (err) {
        // Abort deliberado (cambio de sesión / nuevo envío): no es error de UI.
        if (err instanceof DOMException && err.name === "AbortError") return;
        fail(null);
      }
    },
    [],
  );

  return { live, start, abort, reset, isStreaming: live.phase === "streaming" };
}

/** `JSON.parse` que no tira (devuelve `null` ante data malformada). */
function safeJson(data: string): unknown {
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}
