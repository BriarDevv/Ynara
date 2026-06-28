import { describe, expect, it } from "vitest";

import {
  CHAT_TEXT_MAX_LENGTH,
  ChatMessageSchema,
  ChatRequestSchema,
  ChatResponseSchema,
  SessionSchema,
  StreamReasoningSchema,
} from "./chat";
import { CHAT_ERROR_FALLBACK, chatErrorCopy } from "./chat-copy";

describe("ChatRequestSchema", () => {
  it("acepta un request minimo valido", () => {
    const parsed = ChatRequestSchema.parse({
      text: "hola",
      mode: "productividad",
    });
    expect(parsed.session_id).toBeUndefined();
  });

  it("acepta session_id null (sesion nueva) y un UUID valido", () => {
    expect(ChatRequestSchema.safeParse({ text: "x", mode: "vida", session_id: null }).success).toBe(
      true,
    );
    expect(
      ChatRequestSchema.safeParse({
        text: "x",
        mode: "vida",
        session_id: "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      }).success,
    ).toBe(true);
  });

  it("rechaza texto vacio", () => {
    expect(ChatRequestSchema.safeParse({ text: "", mode: "vida" }).success).toBe(false);
  });

  it("rechaza texto que excede el limite", () => {
    const text = "a".repeat(CHAT_TEXT_MAX_LENGTH + 1);
    expect(ChatRequestSchema.safeParse({ text, mode: "vida" }).success).toBe(false);
  });

  it("rechaza un modo invalido", () => {
    expect(ChatRequestSchema.safeParse({ text: "hola", mode: "inexistente" }).success).toBe(false);
  });
});

describe("ChatMessageSchema", () => {
  it("acepta content null (assistant que solo emite tool_calls)", () => {
    const parsed = ChatMessageSchema.parse({ role: "assistant", content: null });
    expect(parsed.content).toBeNull();
  });

  it("acepta content ausente", () => {
    const parsed = ChatMessageSchema.parse({ role: "user" });
    expect(parsed.content).toBeUndefined();
  });

  it("acepta tool_call_id y name nulos (mirror de str | None)", () => {
    const parsed = ChatMessageSchema.parse({
      role: "tool",
      content: "resultado",
      tool_call_id: null,
      name: null,
    });
    expect(parsed.tool_call_id).toBeNull();
    expect(parsed.name).toBeNull();
  });

  it("rechaza un role invalido", () => {
    expect(ChatMessageSchema.safeParse({ role: "robot" }).success).toBe(false);
  });
});

describe("ChatResponseSchema", () => {
  it("default de actions a [] cuando falta", () => {
    const parsed = ChatResponseSchema.parse({
      text: "respuesta",
      session_id: "sess-1",
      finish_reason: "stop",
    });
    expect(parsed.actions).toEqual([]);
  });

  it("valida actions con result", () => {
    const parsed = ChatResponseSchema.parse({
      text: "ok",
      session_id: "sess-1",
      finish_reason: "stop",
      actions: [{ id: "a1", name: "reminder.create", arguments: {}, result: {} }],
    });
    expect(parsed.actions).toHaveLength(1);
  });

  it("acepta finish_reason null (router no lo seteó)", () => {
    const parsed = ChatResponseSchema.parse({
      text: "ok",
      session_id: "sess-1",
      finish_reason: null,
    });
    expect(parsed.finish_reason).toBeNull();
  });

  it("rechaza si falta finish_reason (es required-pero-nullable)", () => {
    const result = ChatResponseSchema.safeParse({
      text: "ok",
      session_id: "sess-1",
    });
    expect(result.success).toBe(false);
  });
});

describe("SessionSchema", () => {
  it("acepta ended_at null (sesion abierta)", () => {
    const parsed = SessionSchema.parse({
      id: "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      user_id: "0193ffff-bbbb-cccc-dddd-eeeeeeeeeeee",
      mode: "estudio",
      started_at: "2026-05-30T12:00:00Z",
      ended_at: null,
      created_at: "2026-05-30T12:00:00Z",
      updated_at: "2026-05-30T12:00:00Z",
    });
    expect(parsed.ended_at).toBeNull();
  });

  it("rechaza si falta ended_at (es required-pero-nullable)", () => {
    const result = SessionSchema.safeParse({
      id: "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      user_id: "0193ffff-bbbb-cccc-dddd-eeeeeeeeeeee",
      mode: "estudio",
      started_at: "2026-05-30T12:00:00Z",
      created_at: "2026-05-30T12:00:00Z",
      updated_at: "2026-05-30T12:00:00Z",
    });
    expect(result.success).toBe(false);
  });
});

describe("StreamReasoningSchema", () => {
  it("acepta un delta string", () => {
    expect(StreamReasoningSchema.parse({ delta: "pensando" }).delta).toBe("pensando");
  });

  it("rechaza si falta delta", () => {
    expect(StreamReasoningSchema.safeParse({}).success).toBe(false);
  });
});

describe("chatErrorCopy", () => {
  it("mapea un error user-facing a su copy", () => {
    expect(chatErrorCopy("LlmTimeoutError")).toBe("Me colgué un segundo, ¿lo reintentás?");
  });

  it("cae al generico para errores internos", () => {
    expect(chatErrorCopy("ModelNotServedError")).toBe(CHAT_ERROR_FALLBACK);
    expect(chatErrorCopy("MemoryRetrievalError")).toBe(CHAT_ERROR_FALLBACK);
  });

  it("cae al generico para null/undefined/desconocido", () => {
    expect(chatErrorCopy(null)).toBe(CHAT_ERROR_FALLBACK);
    expect(chatErrorCopy(undefined)).toBe(CHAT_ERROR_FALLBACK);
    expect(chatErrorCopy("Inventado")).toBe(CHAT_ERROR_FALLBACK);
  });
});
