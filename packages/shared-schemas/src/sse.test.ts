import { describe, expect, it } from "vitest";

import { createSseParser, parseSseText, SseParseError } from "./sse";

/**
 * Tests del parser SSE del chat. El wire que parsea es el del *endpoint*
 * (`event: <name>\ndata: <json>\n\n`), no el wire interno de vLLM.
 */

const DONE_DATA = JSON.stringify({
  session_id: "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  actions: [],
  finish_reason: "stop",
});

describe("parseSseText", () => {
  it("parsea una secuencia token/token/done", () => {
    const text =
      'event: token\ndata: {"delta": "Hola"}\n\n' +
      'event: token\ndata: {"delta": " mundo"}\n\n' +
      `event: done\ndata: ${DONE_DATA}\n\n`;

    const events = parseSseText(text);

    expect(events).toHaveLength(3);
    expect(events[0]).toEqual({ type: "token", data: { delta: "Hola" } });
    expect(events[1]).toEqual({ type: "token", data: { delta: " mundo" } });
    expect(events[2]?.type).toBe("done");
    if (events[2]?.type === "done") {
      expect(events[2].data.finish_reason).toBe("stop");
      expect(events[2].data.actions).toEqual([]);
    }
  });

  it("parsea un evento error", () => {
    const text = 'event: error\ndata: {"code": "LlmTimeoutError", "message": "timeout"}\n\n';

    const events = parseSseText(text);

    expect(events).toEqual([
      { type: "error", data: { code: "LlmTimeoutError", message: "timeout" } },
    ]);
  });

  it("preserva actions con result en el evento done", () => {
    const data = JSON.stringify({
      session_id: "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      actions: [
        {
          id: "call_1",
          name: "calendar.create_event",
          arguments: { title: "Reunion" },
          result: { status: "ok", event_id: "ev_1" },
        },
      ],
      finish_reason: "tool_calls",
    });
    const events = parseSseText(`event: done\ndata: ${data}\n\n`);

    expect(events).toHaveLength(1);
    if (events[0]?.type === "done") {
      expect(events[0].data.actions[0]?.name).toBe("calendar.create_event");
      expect(events[0].data.actions[0]?.result).toEqual({
        status: "ok",
        event_id: "ev_1",
      });
    }
  });

  it("ignora comentarios, heartbeats y [DONE]", () => {
    const text = ": keep-alive\n\n" + 'event: token\ndata: {"delta": "x"}\n\n' + "data: [DONE]\n\n";

    const events = parseSseText(text);

    expect(events).toEqual([{ type: "token", data: { delta: "x" } }]);
  });

  it("ignora eventos sin nombre conocido (wire interno de vLLM)", () => {
    // Chunk OpenAI-like sin `event:` — el parser lo descarta.
    const text = 'data: {"id":"x","choices":[{"delta":{"content":"Hola"}}]}\n\n';

    expect(parseSseText(text)).toEqual([]);
  });

  it("tolera CRLF", () => {
    const text = 'event: token\r\ndata: {"delta": "Hola"}\r\n\r\n';
    expect(parseSseText(text)).toEqual([{ type: "token", data: { delta: "Hola" } }]);
  });

  it("tolera data sin espacio tras los dos puntos", () => {
    const text = 'event: token\ndata:{"delta": "Hola"}\n\n';
    expect(parseSseText(text)).toEqual([{ type: "token", data: { delta: "Hola" } }]);
  });
});

describe("createSseParser (incremental)", () => {
  it("buffferea un evento partido entre chunks", () => {
    const parser = createSseParser();

    expect(parser.push("event: token\nda")).toEqual([]);
    expect(parser.push('ta: {"delta": "Ho')).toEqual([]);
    const events = parser.push('la"}\n\n');

    expect(events).toEqual([{ type: "token", data: { delta: "Hola" } }]);
  });

  it("emite varios eventos llegados en un solo chunk", () => {
    const parser = createSseParser();
    const events = parser.push(
      'event: token\ndata: {"delta": "a"}\n\nevent: token\ndata: {"delta": "b"}\n\n',
    );
    expect(events).toHaveLength(2);
  });

  it("flush parsea un bloque final sin separador de cierre", () => {
    const parser = createSseParser();
    expect(parser.push('event: token\ndata: {"delta": "z"}')).toEqual([]);
    expect(parser.flush()).toEqual([{ type: "token", data: { delta: "z" } }]);
  });

  it("flush no rompe con buffer vacio", () => {
    const parser = createSseParser();
    expect(parser.flush()).toEqual([]);
  });
});

describe("errores de parseo", () => {
  it("lanza SseParseError si data no es JSON", () => {
    expect(() => parseSseText("event: token\ndata: no-json\n\n")).toThrow(SseParseError);
  });

  it("lanza SseParseError si data no matchea el contrato", () => {
    // token sin delta
    expect(() => parseSseText('event: token\ndata: {"foo": 1}\n\n')).toThrow(SseParseError);
  });

  it("no expone el contenido en el message, solo en raw", () => {
    try {
      parseSseText('event: token\ndata: {"secreto": "pii"}\n\n');
      expect.unreachable("debio lanzar");
    } catch (err) {
      expect(err).toBeInstanceOf(SseParseError);
      if (err instanceof SseParseError) {
        expect(err.message).not.toContain("pii");
        expect(err.raw).toContain("pii");
      }
    }
  });
});
