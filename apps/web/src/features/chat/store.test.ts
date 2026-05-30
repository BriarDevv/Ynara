import { beforeEach, describe, expect, it } from "vitest";
import { useChatStore } from "./store";

// jsdom provee localStorage real; el persist de zustand lo usa directo.
beforeEach(() => {
  useChatStore.getState().reset();
  localStorage.clear();
});

describe("useChatStore", () => {
  it("crea una sesión en el modo dado con mensajes vacíos", () => {
    const id = useChatStore.getState().createSession("estudio");
    const { sessions, messages } = useChatStore.getState();

    expect(sessions[id]?.mode).toBe("estudio");
    expect(sessions[id]?.id).toBe(id);
    expect(messages[id]).toEqual([]);
  });

  it("appendUserMessage agrega un mensaje optimistic en estado sending", () => {
    const sid = useChatStore.getState().createSession("vida");
    const mid = useChatStore.getState().appendUserMessage(sid, "hola");

    const msg = useChatStore.getState().messages[sid]?.[0];
    expect(msg?.id).toBe(mid);
    expect(msg?.role).toBe("user");
    expect(msg?.text).toBe("hola");
    expect(msg?.status).toBe("sending");
  });

  it("setMessageStatus transiciona sending → done", () => {
    const sid = useChatStore.getState().createSession("vida");
    const mid = useChatStore.getState().appendUserMessage(sid, "hola");

    useChatStore.getState().setMessageStatus(sid, mid, "done");
    expect(useChatStore.getState().messages[sid]?.[0]?.status).toBe("done");
  });

  it("setMessageStatus marca error con su código", () => {
    const sid = useChatStore.getState().createSession("vida");
    const mid = useChatStore.getState().appendUserMessage(sid, "hola");

    useChatStore.getState().setMessageStatus(sid, mid, "error", "LlmTimeoutError");
    const msg = useChatStore.getState().messages[sid]?.[0];
    expect(msg?.status).toBe("error");
    expect(msg?.errorCode).toBe("LlmTimeoutError");
  });

  it("applyChatResponse cierra el optimistic del user y agrega el assistant con actions", () => {
    const sid = useChatStore.getState().createSession("productividad");
    const userMsgId = useChatStore.getState().appendUserMessage(sid, "agendá algo");

    useChatStore.getState().applyChatResponse(sid, userMsgId, {
      text: "listo",
      session_id: sid,
      actions: [{ id: "a1", name: "calendar.create_event", arguments: {}, result: {} }],
    });

    const list = useChatStore.getState().messages[sid] ?? [];
    expect(list).toHaveLength(2);
    expect(list[0]?.role).toBe("user");
    expect(list[0]?.status).toBe("done");
    const assistant = list.at(-1);
    expect(assistant?.role).toBe("assistant");
    expect(assistant?.text).toBe("listo");
    expect(assistant?.status).toBe("done");
    expect(assistant?.actions).toHaveLength(1);
  });

  it("flujo optimistic completo: sin mensajes colgados en sending", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userMsgId = useChatStore.getState().appendUserMessage(sid, "hola");
    expect(useChatStore.getState().messages[sid]?.[0]?.status).toBe("sending");

    useChatStore.getState().applyChatResponse(sid, userMsgId, {
      text: "buenas",
      session_id: sid,
      actions: [],
    });

    const list = useChatStore.getState().messages[sid] ?? [];
    expect(list.some((m) => m.status === "sending")).toBe(false);
  });

  it("applyChatResponse deja actions undefined cuando viene vacío (Gemma)", () => {
    const sid = useChatStore.getState().createSession("estudio");
    const userMsgId = useChatStore.getState().appendUserMessage(sid, "explicame algo");
    useChatStore.getState().applyChatResponse(sid, userMsgId, {
      text: "respuesta",
      session_id: sid,
      actions: [],
    });
    expect(useChatStore.getState().messages[sid]?.at(-1)?.actions).toBeUndefined();
  });

  it("appendMessage toca el updatedAt de la sesión", () => {
    const sid = useChatStore.getState().createSession("vida");
    const before = useChatStore.getState().sessions[sid]?.updatedAt ?? 0;
    useChatStore.getState().appendUserMessage(sid, "hola");
    const after = useChatStore.getState().sessions[sid]?.updatedAt ?? 0;
    expect(after).toBeGreaterThanOrEqual(before);
  });

  it("ids de sesión y de mensaje son distintos", () => {
    const s1 = useChatStore.getState().createSession("vida");
    const s2 = useChatStore.getState().createSession("vida");
    expect(s1).not.toBe(s2);
    const m1 = useChatStore.getState().appendUserMessage(s1, "a");
    const m2 = useChatStore.getState().appendUserMessage(s1, "b");
    expect(m1).not.toBe(m2);
  });
});
