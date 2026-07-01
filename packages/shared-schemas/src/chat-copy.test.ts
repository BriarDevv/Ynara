import { describe, expect, it } from "vitest";
import { CHAT_PAUSED_COPY, chatErrorCopy, chatPausedCopy } from "./chat-copy";

describe("chatPausedCopy", () => {
  it("devuelve el copy honesto de 'IA no disponible'", () => {
    expect(chatPausedCopy()).toBe(CHAT_PAUSED_COPY);
  });

  it("es genérico-honesto: no menciona una causa concreta (sirve para pausa y overflow)", () => {
    const copy = chatPausedCopy().toLowerCase();
    expect(copy).toContain("no está disponible");
    // No debe atarse a una causa puntual que sería mentira en el caso de overflow.
    expect(copy).not.toContain("ollama");
    expect(copy).not.toContain("técnico");
  });

  it("es distinto del copy de error (no es un fallo del turno)", () => {
    expect(chatPausedCopy()).not.toBe(chatErrorCopy(undefined));
    expect(chatPausedCopy()).not.toBe(chatErrorCopy("LlmTimeoutError"));
  });
});
