import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { sendChatMessage } from "./chat";

vi.mock("./api", () => ({
  api: { post: vi.fn() },
}));

const mockedPost = vi.mocked(api.post);

afterEach(() => {
  vi.clearAllMocks();
});

describe("sendChatMessage", () => {
  it("postea a /v1/chat y devuelve el ChatResponse validado", async () => {
    mockedPost.mockResolvedValueOnce({
      text: "hola",
      actions: [],
      session_id: "sess-1",
    });

    const res = await sendChatMessage({ text: "hola", mode: "vida" });

    expect(mockedPost).toHaveBeenCalledWith("/v1/chat", { text: "hola", mode: "vida" });
    expect(res.text).toBe("hola");
    expect(res.actions).toEqual([]);
  });

  it("aplica el default actions:[] cuando el backend lo omite", async () => {
    mockedPost.mockResolvedValueOnce({ text: "ok", session_id: "s" });
    const res = await sendChatMessage({ text: "x", mode: "estudio" });
    expect(res.actions).toEqual([]);
  });

  it("tira si la respuesta no matchea el contrato (Zod)", async () => {
    mockedPost.mockResolvedValueOnce({ text: 123, session_id: "s" });
    await expect(sendChatMessage({ text: "x", mode: "vida" })).rejects.toThrow();
  });
});
