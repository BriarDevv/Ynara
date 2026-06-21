import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useBackendSessionStore } from "./backendSessions";
import { useChatStore } from "./store";
import { useChatStream } from "./useChatStream";

/**
 * Tests del hook de streaming. No hay `setupServer` de MSW en los unit tests
 * (se mockea en la frontera de fetch, igual que `lib/chat.test.ts` mockea
 * `./api`): acá stubbeamos `global.fetch` con un `Response`-like cuyo `.body`
 * es un `ReadableStream` armado desde un string SSE (encodeado con TextEncoder).
 */

const encoder = new TextEncoder();

/** ReadableStream que emite los chunks dados (ya como strings SSE) en orden. */
function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

/** Stub de un Response ok con un body de stream. */
function okResponse(chunks: string[]): Response {
  return {
    ok: true,
    body: streamFromChunks(chunks),
  } as unknown as Response;
}

/** Stub de un Response no-ok con un body JSON de error. */
function errorResponse(status: number, body: unknown): Response {
  return {
    ok: false,
    status,
    body: null,
    json: async () => body,
  } as unknown as Response;
}

function setupSession(mode: "vida" | "productividad" = "vida") {
  const sessionId = useChatStore.getState().createSession(mode);
  const userMessageId = useChatStore.getState().appendUserMessage(sessionId, "hola");
  return { sessionId, userMessageId };
}

function assistantOf(sessionId: string) {
  return useChatStore.getState().messages[sessionId]?.find((m) => m.role === "assistant");
}

beforeEach(() => {
  useChatStore.getState().reset();
  useBackendSessionStore.getState().reset();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useChatStream", () => {
  it("acumula los deltas en orden y transiciona streaming → done con actions", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        okResponse([
          'event: token\ndata: {"delta":"Hola"}\n\n',
          'event: token\ndata: {"delta":" mundo"}\n\n',
          'event: done\ndata: {"session_id":"s1","actions":[{"id":"a1","name":"calendar.create_event","arguments":{},"result":{}}],"finish_reason":"stop"}\n\n',
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession("productividad");
    const { result } = renderHook(() => useChatStream(sessionId));

    await act(async () => {
      await result.current.send(
        { text: "hola", mode: "productividad", session_id: sessionId },
        userMessageId,
      );
    });

    const assistant = assistantOf(sessionId);
    expect(assistant?.text).toBe("Hola mundo");
    expect(assistant?.status).toBe("done");
    expect(assistant?.actions).toHaveLength(1);
    expect(useChatStore.getState().streamStatus).toBe("idle");
    expect(result.current.isStreaming).toBe(false);
  });

  it("adopta el session_id real del evento done (mapeo localId→backendId)", async () => {
    // El backend devuelve en `done` el id REAL de la ChatSession que creó (el
    // primer turno mandó session_id:null). El hook debe persistir ese id para que
    // los turnos siguientes lo reusen y encadenen la conversación.
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        okResponse([
          'event: token\ndata: {"delta":"hola"}\n\n',
          'event: done\ndata: {"session_id":"backend-real-id","actions":[],"finish_reason":"stop"}\n\n',
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    expect(useBackendSessionStore.getState().getBackendSessionId(sessionId)).toBeNull();

    const { result } = renderHook(() => useChatStream(sessionId));
    await act(async () => {
      // 1er turno: session_id null (el backend crea la sesión).
      await result.current.send({ text: "hola", mode: "vida", session_id: null }, userMessageId);
    });

    expect(useBackendSessionStore.getState().getBackendSessionId(sessionId)).toBe(
      "backend-real-id",
    );
  });

  it("manda los headers de SSE y el Bearer del store", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        okResponse([
          'event: done\ndata: {"session_id":"s","actions":[],"finish_reason":"stop"}\n\n',
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);
    // Token en el store de usuario → debe viajar como Authorization.
    const { useUserStore } = await import("@/stores/user");
    useUserStore.getState().setAuth({ userId: "u1", token: "tok-123", isEphemeral: false });

    const { sessionId, userMessageId } = setupSession();
    const { result } = renderHook(() => useChatStream(sessionId));
    await act(async () => {
      await result.current.send(
        { text: "hola", mode: "vida", session_id: sessionId },
        userMessageId,
      );
    });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = init.headers as Headers;
    expect(headers.get("Accept")).toBe("text/event-stream");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Authorization")).toBe("Bearer tok-123");
    useUserStore.getState().reset();
  });

  it("reconstruye un token partido entre dos chunks del reader (parser incremental)", async () => {
    // El bloque del token se corta en medio del JSON: el primer chunk deja
    // un bloque incompleto que el parser bufferea hasta el segundo.
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        okResponse([
          'event: token\ndata: {"del',
          'ta":"partido"}\n\nevent: done\ndata: {"session_id":"s","actions":[],"finish_reason":"stop"}\n\n',
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    const { result } = renderHook(() => useChatStream(sessionId));
    await act(async () => {
      await result.current.send(
        { text: "hola", mode: "vida", session_id: sessionId },
        userMessageId,
      );
    });

    const assistant = assistantOf(sessionId);
    expect(assistant?.text).toBe("partido");
    expect(assistant?.status).toBe("done");
  });

  it("un evento error mid-stream llama failAssistantStream", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        okResponse([
          'event: token\ndata: {"delta":"empez"}\n\n',
          'event: error\ndata: {"code":"LlmError","message":"reventó"}\n\n',
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    const { result } = renderHook(() => useChatStream(sessionId));
    await act(async () => {
      await result.current.send(
        { text: "hola", mode: "vida", session_id: sessionId },
        userMessageId,
      );
    });

    // Hubo texto parcial → el assistant queda en error con su parcial, y el
    // user queda error para habilitar el retry.
    const list = useChatStore.getState().messages[sessionId] ?? [];
    const assistant = list.find((m) => m.role === "assistant");
    expect(assistant?.status).toBe("error");
    expect(assistant?.text).toBe("empez");
    expect(assistant?.errorCode).toBe("LlmError");
    expect(list.find((m) => m.role === "user")?.status).toBe("error");
    expect(useChatStore.getState().streamStatus).toBe("error");
  });

  it("un response no-ok falla con el code del body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(errorResponse(503, { error: "LlmUnavailable", detail: "down" }));
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    const { result } = renderHook(() => useChatStream(sessionId));
    await act(async () => {
      await result.current.send(
        { text: "hola", mode: "vida", session_id: sessionId },
        userMessageId,
      );
    });

    // Sin tokens → placeholder descartado, user en error con el code del body.
    const list = useChatStore.getState().messages[sessionId] ?? [];
    expect(list.find((m) => m.role === "assistant")).toBeUndefined();
    const user = list.find((m) => m.role === "user");
    expect(user?.status).toBe("error");
    expect(user?.errorCode).toBe("LlmUnavailable");
  });

  it("cancel() aborta un stream colgado y marca canceled", async () => {
    // Stream que emite un token y después queda colgado: el siguiente
    // `reader.read()` queda pendiente hasta que el abort del signal lo rechaza
    // con AbortError (modela el comportamiento real de fetch + body stream).
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const signal = init.signal;
      let emitted = false;
      const body = new ReadableStream<Uint8Array>({
        pull(controller) {
          if (!emitted) {
            emitted = true;
            controller.enqueue(encoder.encode('event: token\ndata: {"delta":"hola"}\n\n'));
            return;
          }
          // Segundo pull: queda pendiente hasta el abort.
          return new Promise<void>((_resolve, reject) => {
            signal?.addEventListener("abort", () => {
              reject(new DOMException("Aborted", "AbortError"));
            });
          });
        },
      });
      return Promise.resolve({ ok: true, body } as unknown as Response);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    const { result } = renderHook(() => useChatStream(sessionId));
    // Capturamos refs estables: tras el primer render el hook no recrea send/cancel.
    const { send, cancel } = result.current;

    let sendPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      sendPromise = send({ text: "hola", mode: "vida", session_id: sessionId }, userMessageId);
      // Dejamos que llegue el primer token antes de cancelar.
      await new Promise((r) => setTimeout(r, 0));
    });

    await act(async () => {
      cancel();
      await sendPromise;
    });

    const assistant = assistantOf(sessionId);
    expect(assistant?.status).toBe("canceled");
    expect(assistant?.text).toBe("hola");
    expect(useChatStore.getState().streamStatus).toBe("idle");
  });

  it("ignora un segundo send mientras hay uno en vuelo (single in-flight)", async () => {
    // Stream que emite un token y queda colgado: mantiene el primer send en
    // vuelo mientras disparamos el segundo.
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const signal = init.signal;
      let emitted = false;
      const body = new ReadableStream<Uint8Array>({
        pull(controller) {
          if (!emitted) {
            emitted = true;
            controller.enqueue(encoder.encode('event: token\ndata: {"delta":"x"}\n\n'));
            return;
          }
          return new Promise<void>((_resolve, reject) => {
            signal?.addEventListener("abort", () => {
              reject(new DOMException("Aborted", "AbortError"));
            });
          });
        },
      });
      return Promise.resolve({ ok: true, body } as unknown as Response);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    const { result } = renderHook(() => useChatStream(sessionId));
    const { send, cancel } = result.current;

    let first: Promise<void> = Promise.resolve();
    await act(async () => {
      first = send({ text: "uno", mode: "vida", session_id: sessionId }, userMessageId);
      await new Promise((r) => setTimeout(r, 0));
      // Segundo send debe ser no-op (un solo stream en vuelo).
      await send({ text: "dos", mode: "vida", session_id: sessionId }, userMessageId);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Limpieza: abortamos el stream colgado para no dejar el test pendiente.
    await act(async () => {
      cancel();
      await first;
    });
  });

  it("un data malformado tira SseParseError y cierra en stream_parse_error", async () => {
    // `data:` no es JSON válido → el parser tira SseParseError dentro de
    // `parser.push`, que el hook mapea a errorCode "stream_parse_error".
    const fetchMock = vi
      .fn()
      .mockResolvedValue(okResponse(["event: token\ndata: {no es json}\n\n"]));
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    const { result } = renderHook(() => useChatStream(sessionId));
    await act(async () => {
      await result.current.send(
        { text: "hola", mode: "vida", session_id: sessionId },
        userMessageId,
      );
    });

    // El throw ocurre antes de cualquier token → placeholder vacío descartado,
    // user en error con el code del parser para habilitar el retry.
    const list = useChatStore.getState().messages[sessionId] ?? [];
    expect(list.find((m) => m.role === "assistant")).toBeUndefined();
    const user = list.find((m) => m.role === "user");
    expect(user?.status).toBe("error");
    expect(user?.errorCode).toBe("stream_parse_error");
    expect(useChatStore.getState().streamStatus).toBe("error");
  });

  it("EOF sin evento done cierra el placeholder colgado en done", async () => {
    // El stream emite un token y corta (reader done) sin `done` ni `error`:
    // el hook fuerza el cierre del placeholder que quedó en "streaming".
    const fetchMock = vi
      .fn()
      .mockResolvedValue(okResponse(['event: token\ndata: {"delta":"hola"}\n\n']));
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    const { result } = renderHook(() => useChatStream(sessionId));
    await act(async () => {
      await result.current.send(
        { text: "hola", mode: "vida", session_id: sessionId },
        userMessageId,
      );
    });

    const assistant = assistantOf(sessionId);
    expect(assistant?.text).toBe("hola");
    expect(assistant?.status).toBe("done");
    expect(useChatStore.getState().streamStatus).toBe("idle");
  });

  it("unmount aborta el stream en vuelo y marca el assistant canceled", async () => {
    // Stream que emite un token y queda colgado hasta el abort. Al desmontar,
    // el cleanup cancela: aborta el signal y marca el assistant "canceled"
    // (status verídico), en vez de dejarlo colgado en "streaming".
    let captured: AbortSignal | undefined;
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      captured = init.signal ?? undefined;
      let emitted = false;
      const body = new ReadableStream<Uint8Array>({
        pull(controller) {
          if (!emitted) {
            emitted = true;
            controller.enqueue(encoder.encode('event: token\ndata: {"delta":"hola"}\n\n'));
            return;
          }
          return new Promise<void>((_resolve, reject) => {
            init.signal?.addEventListener("abort", () => {
              reject(new DOMException("Aborted", "AbortError"));
            });
          });
        },
      });
      return Promise.resolve({ ok: true, body } as unknown as Response);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { sessionId, userMessageId } = setupSession();
    const { result, unmount } = renderHook(() => useChatStream(sessionId));

    let sendPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      sendPromise = result.current.send(
        { text: "hola", mode: "vida", session_id: sessionId },
        userMessageId,
      );
      await new Promise((r) => setTimeout(r, 0));
    });

    await act(async () => {
      unmount();
      await sendPromise;
    });

    expect(captured?.aborted).toBe(true);
    const assistant = assistantOf(sessionId);
    expect(assistant?.status).toBe("canceled");
    expect(assistant?.text).toBe("hola");
  });
});
