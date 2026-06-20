import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePlaygroundStream } from "./usePlaygroundStream";

/**
 * Tests del hook de streaming SSE del Playground. Mockeamos `fetch` con una
 * `Response` cuyo body es un `ReadableStream` de frames SSE, y ejercitamos cada
 * rama del parser: token / reasoning / done / error, precedencia del thinking,
 * frames partidos entre chunks del reader, JSON malformado, no-ok y cierre sin
 * done. Es el guard del camino más complejo del panel rediseñado (el blueprint
 * sólo lo pinta token-por-token si este parser es correcto).
 */

const encoder = new TextEncoder();

function sseResponse(frames: readonly string[], status = 200): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(encoder.encode(f));
      controller.close();
    },
  });
  return new Response(stream, {
    status,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function mockFetch(resp: Response): ReturnType<typeof vi.fn> {
  const fn = vi.fn().mockResolvedValue(resp);
  vi.stubGlobal("fetch", fn);
  return fn;
}

const DONE_BASE = {
  finish_reason: "stop",
  model_name: "qwen",
  completion_tokens: 1,
  latency_ms: 100,
  tokens_per_second: 10,
  thinking_used: true,
};

function doneFrame(extra: Record<string, unknown> = {}): string {
  return `event: done\ndata: ${JSON.stringify({ ...DONE_BASE, thinking: null, ...extra })}\n\n`;
}

const INPUT = {
  model: "qwen",
  message: "hola",
  params: { max_tokens: 64, temperature: 0.3, low_perf: false },
  thinking: true,
} as const;

describe("usePlaygroundStream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("acumula tokens y resuelve onComplete con el texto, y vuelve a idle", async () => {
    mockFetch(
      sseResponse([
        `event: token\ndata: {"delta":"Hola"}\n\n`,
        `event: token\ndata: {"delta":", mundo"}\n\n`,
        doneFrame(),
      ]),
    );
    const onComplete = vi.fn();
    const onError = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete, onError });
    });

    expect(onError).not.toHaveBeenCalled();
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete.mock.lastCall?.[0].text).toBe("Hola, mundo");
    expect(result.current.live.phase).toBe("idle");
    expect(result.current.isStreaming).toBe(false);
  });

  it("captura el canal reasoning como thinking final cuando done no lo trae", async () => {
    mockFetch(
      sseResponse([
        `event: reasoning\ndata: {"delta":"Pen"}\n\n`,
        `event: reasoning\ndata: {"delta":"sando"}\n\n`,
        `event: token\ndata: {"delta":"Listo"}\n\n`,
        doneFrame({ thinking: null }),
      ]),
    );
    const onComplete = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete, onError: vi.fn() });
    });

    const final = onComplete.mock.lastCall?.[0];
    expect(final.text).toBe("Listo");
    expect(final.thinking).toBe("Pensando");
  });

  it("done.thinking del server tiene precedencia sobre el reasoning en vivo", async () => {
    mockFetch(
      sseResponse([
        `event: reasoning\ndata: {"delta":"en vivo"}\n\n`,
        doneFrame({ thinking: "autoritativo del server" }),
      ]),
    );
    const onComplete = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete, onError: vi.fn() });
    });

    expect(onComplete.mock.lastCall?.[0].thinking).toBe("autoritativo del server");
  });

  it("reasoning-only sin texto: thinking poblado y texto vacío", async () => {
    mockFetch(
      sseResponse([
        `event: reasoning\ndata: {"delta":"solo pienso"}\n\n`,
        doneFrame({ completion_tokens: 0, thinking: null }),
      ]),
    );
    const onComplete = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete, onError: vi.fn() });
    });

    const final = onComplete.mock.lastCall?.[0];
    expect(final.text).toBe("");
    expect(final.thinking).toBe("solo pienso");
  });

  it("un evento error dispara onError(null) y deja la fase en error", async () => {
    mockFetch(
      sseResponse([
        `event: error\ndata: {"code":"stream_error","message":"No se pudo completar la respuesta"}\n\n`,
      ]),
    );
    const onComplete = vi.fn();
    const onError = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete, onError });
    });

    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(null);
    expect(result.current.live.phase).toBe("error");
  });

  it("respuesta no-ok (422) -> onError(status)", async () => {
    mockFetch(new Response("{}", { status: 422 }));
    const onError = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete: vi.fn(), onError });
    });

    expect(onError).toHaveBeenCalledWith(422);
  });

  it("parsea un frame partido entre dos chunks del reader", async () => {
    mockFetch(
      sseResponse([
        `event: token\nda`, // chunk 1: frame incompleto
        `ta: {"delta":"ok"}\n\n`, // chunk 2: completa el frame
        doneFrame(),
      ]),
    );
    const onComplete = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete, onError: vi.fn() });
    });

    expect(onComplete.mock.lastCall?.[0].text).toBe("ok");
  });

  it("ignora un frame con JSON malformado y sigue parseando", async () => {
    mockFetch(
      sseResponse([
        `event: token\ndata: {no es json}\n\n`,
        `event: token\ndata: {"delta":"bien"}\n\n`,
        doneFrame(),
      ]),
    );
    const onComplete = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete, onError: vi.fn() });
    });

    expect(onComplete.mock.lastCall?.[0].text).toBe("bien");
  });

  it("stream que cierra sin done -> onError(null)", async () => {
    mockFetch(sseResponse([`event: token\ndata: {"delta":"a"}\n\n`]));
    const onComplete = vi.fn();
    const onError = vi.fn();
    const { result } = renderHook(() => usePlaygroundStream());

    await act(async () => {
      await result.current.start(INPUT, { onComplete, onError });
    });

    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(null);
  });
});
