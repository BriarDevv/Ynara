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
      finish_reason: "stop",
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
      finish_reason: "stop",
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
      finish_reason: "stop",
    });
    expect(useChatStore.getState().messages[sid]?.at(-1)?.actions).toBeUndefined();
  });

  it("applyChatResponse con finish_reason='degraded' marca degraded y descarta el texto enlatado", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userMsgId = useChatStore.getState().appendUserMessage(sid, "hola");
    useChatStore.getState().applyChatResponse(sid, userMsgId, {
      text: "Estoy con un problema tecnico, proba en un ratito.",
      session_id: sid,
      actions: [],
      finish_reason: "degraded",
    });

    const assistant = useChatStore.getState().messages[sid]?.at(-1);
    expect(assistant?.role).toBe("assistant");
    expect(assistant?.status).toBe("degraded");
    // El texto enlatado del backend NO se conserva (sería una respuesta mentirosa).
    expect(assistant?.text).toBe("");
    expect(assistant?.actions).toBeUndefined();
    // El user del turno igual queda cerrado (no es un error del usuario).
    expect(useChatStore.getState().messages[sid]?.[0]?.status).toBe("done");
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

describe("useChatStore — streaming (W3)", () => {
  it("startAssistantStream cierra el user y crea el placeholder en streaming", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");

    const assistantId = useChatStore.getState().startAssistantStream(sid, userId);

    const list = useChatStore.getState().messages[sid] ?? [];
    expect(list).toHaveLength(2);
    expect(list[0]?.id).toBe(userId);
    expect(list[0]?.status).toBe("done");
    const assistant = list.at(-1);
    expect(assistant?.id).toBe(assistantId);
    expect(assistant?.role).toBe("assistant");
    expect(assistant?.text).toBe("");
    expect(assistant?.status).toBe("streaming");
    expect(useChatStore.getState().streamStatus).toBe("streaming");
  });

  it("startAssistantStream inicializa reasoning vacío", () => {
    const sid = useChatStore.getState().createSession("memoria");
    const userId = useChatStore.getState().appendUserMessage(sid, "acordate de esto");

    useChatStore.getState().startAssistantStream(sid, userId);

    expect(useChatStore.getState().messages[sid]?.at(-1)?.reasoning).toBe("");
  });

  it("appendReasoningDelta acumula el razonamiento sin tocar el texto", () => {
    const sid = useChatStore.getState().createSession("productividad");
    const userId = useChatStore.getState().appendUserMessage(sid, "agendá algo");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);

    useChatStore.getState().appendReasoningDelta(sid, aid, "Primero ");
    useChatStore.getState().appendReasoningDelta(sid, aid, "reviso ");
    useChatStore.getState().appendReasoningDelta(sid, aid, "el calendario");

    const assistant = useChatStore.getState().messages[sid]?.at(-1);
    expect(assistant?.reasoning).toBe("Primero reviso el calendario");
    // El razonamiento es un canal aparte: no contamina el texto de la respuesta.
    expect(assistant?.text).toBe("");
    expect(assistant?.status).toBe("streaming");
  });

  it("reasoning no se persiste en el storage (efímero)", () => {
    const sid = useChatStore.getState().createSession("memoria");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);
    useChatStore.getState().appendReasoningDelta(sid, aid, "RAZONAMIENTO_LARGO_SECRETO");

    const persisted = localStorage.getItem("ynara.chat");
    expect(persisted).not.toBeNull();
    // Ni la cadena de razonamiento ni la clave `reasoning` llegan al disco.
    expect(persisted as string).not.toContain("RAZONAMIENTO_LARGO_SECRETO");
    expect(persisted as string).not.toContain("reasoning");
  });

  it("appendStreamDelta acumula el texto en orden", () => {
    const sid = useChatStore.getState().createSession("estudio");
    const userId = useChatStore.getState().appendUserMessage(sid, "tema");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);

    useChatStore.getState().appendStreamDelta(sid, aid, "Hola");
    useChatStore.getState().appendStreamDelta(sid, aid, " ");
    useChatStore.getState().appendStreamDelta(sid, aid, "mundo");

    const assistant = useChatStore.getState().messages[sid]?.at(-1);
    expect(assistant?.text).toBe("Hola mundo");
    expect(assistant?.status).toBe("streaming");
  });

  it("finishAssistantStream cierra en done con actions y deja streamStatus idle", () => {
    const sid = useChatStore.getState().createSession("productividad");
    const userId = useChatStore.getState().appendUserMessage(sid, "agendá");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);
    useChatStore.getState().appendStreamDelta(sid, aid, "listo");

    useChatStore.getState().finishAssistantStream(sid, aid, {
      actions: [{ id: "a1", name: "calendar.create_event", arguments: {}, result: {} }],
    });

    const assistant = useChatStore.getState().messages[sid]?.at(-1);
    expect(assistant?.status).toBe("done");
    expect(assistant?.text).toBe("listo");
    expect(assistant?.actions).toHaveLength(1);
    expect(useChatStore.getState().streamStatus).toBe("idle");
  });

  it("finishAssistantStream sin actions deja actions undefined (Gemma)", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "che");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);
    useChatStore.getState().appendStreamDelta(sid, aid, "respuesta");

    useChatStore.getState().finishAssistantStream(sid, aid, { actions: [] });

    const assistant = useChatStore.getState().messages[sid]?.at(-1);
    expect(assistant?.status).toBe("done");
    expect(assistant?.actions).toBeUndefined();
  });

  it("finishAssistantStream con finishReason='degraded' marca degraded, descarta el texto y deja idle", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);
    // Durante el stream se acumuló el texto enlatado del backend degradado.
    useChatStore.getState().appendStreamDelta(sid, aid, "Estoy con un problema tecnico");

    useChatStore.getState().finishAssistantStream(sid, aid, {
      actions: [],
      finishReason: "degraded",
    });

    const assistant = useChatStore.getState().messages[sid]?.at(-1);
    expect(assistant?.status).toBe("degraded");
    // El texto enlatado se descarta (la UI muestra el copy honesto, no la mentira).
    expect(assistant?.text).toBe("");
    expect(assistant?.actions).toBeUndefined();
    // Degradado NO es error: streamStatus vuelve a idle (composer habilitado).
    expect(useChatStore.getState().streamStatus).toBe("idle");
    // El user del turno queda "done" (lo cerró startAssistantStream), no error.
    expect(useChatStore.getState().messages[sid]?.find((m) => m.id === userId)?.status).toBe(
      "done",
    );
  });

  it("finishAssistantStream con finishReason='stop' sigue cerrando en done (regresión)", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);
    useChatStore.getState().appendStreamDelta(sid, aid, "respuesta real");

    useChatStore.getState().finishAssistantStream(sid, aid, { actions: [], finishReason: "stop" });

    const assistant = useChatStore.getState().messages[sid]?.at(-1);
    expect(assistant?.status).toBe("done");
    expect(assistant?.text).toBe("respuesta real");
  });

  it("failAssistantStream SIN texto descarta el placeholder y marca el user error", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);

    useChatStore.getState().failAssistantStream(sid, aid, "LlmTimeoutError");

    const list = useChatStore.getState().messages[sid] ?? [];
    // El placeholder vacío se descartó: solo queda el user marcado error.
    expect(list).toHaveLength(1);
    expect(list[0]?.id).toBe(userId);
    expect(list[0]?.role).toBe("user");
    expect(list[0]?.status).toBe("error");
    expect(list[0]?.errorCode).toBe("LlmTimeoutError");
    expect(useChatStore.getState().streamStatus).toBe("error");
  });

  it("failAssistantStream CON texto parcial conserva el assistant en error + user error", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);
    useChatStore.getState().appendStreamDelta(sid, aid, "Empecé a respon");

    useChatStore.getState().failAssistantStream(sid, aid, "LlmError");

    const list = useChatStore.getState().messages[sid] ?? [];
    expect(list).toHaveLength(2);
    const assistant = list.find((m) => m.id === aid);
    expect(assistant?.status).toBe("error");
    expect(assistant?.text).toBe("Empecé a respon");
    const user = list.find((m) => m.id === userId);
    expect(user?.status).toBe("error");
    expect(user?.errorCode).toBe("LlmError");
    expect(useChatStore.getState().streamStatus).toBe("error");
  });

  it("cancelAssistantStream conserva el parcial y marca canceled + idle", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);
    useChatStore.getState().appendStreamDelta(sid, aid, "texto parcial");

    useChatStore.getState().cancelAssistantStream(sid, aid);

    const assistant = useChatStore.getState().messages[sid]?.at(-1);
    expect(assistant?.status).toBe("canceled");
    expect(assistant?.text).toBe("texto parcial");
    expect(useChatStore.getState().streamStatus).toBe("idle");
  });

  it("cancelAssistantStream SIN texto descarta el placeholder vacío", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");
    const aid = useChatStore.getState().startAssistantStream(sid, userId);

    // Cancel antes del primer token: no hay parcial que conservar.
    useChatStore.getState().cancelAssistantStream(sid, aid);

    const list = useChatStore.getState().messages[sid] ?? [];
    expect(list.find((m) => m.id === aid)).toBeUndefined();
    // El user del turno queda como lo dejó startAssistantStream (done), sin
    // burbuja de assistant vacía detrás.
    expect(list).toHaveLength(1);
    expect(list[0]?.role).toBe("user");
    expect(useChatStore.getState().streamStatus).toBe("idle");
  });

  it("streamStatus no se persiste (no aparece en el storage)", () => {
    const sid = useChatStore.getState().createSession("vida");
    const userId = useChatStore.getState().appendUserMessage(sid, "hola");
    useChatStore.getState().startAssistantStream(sid, userId);

    const persisted = localStorage.getItem("ynara.chat");
    expect(persisted).not.toBeNull();
    expect(persisted as string).not.toContain("streamStatus");
  });

  it("failAssistantStream marca el user del turno que falló, no el último user global", () => {
    const sid = useChatStore.getState().createSession("vida");
    // Turno 1 completo y OK.
    const u1 = useChatStore.getState().appendUserMessage(sid, "turno 1");
    const a1 = useChatStore.getState().startAssistantStream(sid, u1);
    useChatStore.getState().appendStreamDelta(sid, a1, "ok");
    useChatStore.getState().finishAssistantStream(sid, a1);
    // Turno 2 arranca y falla sin texto.
    const u2 = useChatStore.getState().appendUserMessage(sid, "turno 2");
    const a2 = useChatStore.getState().startAssistantStream(sid, u2);
    useChatStore.getState().failAssistantStream(sid, a2, "LlmError");

    const list = useChatStore.getState().messages[sid] ?? [];
    // El user del turno 1 NO se toca; el del turno 2 (el que falló) queda error.
    expect(list.find((m) => m.id === u1)?.status).toBe("done");
    expect(list.find((m) => m.id === u2)?.status).toBe("error");
    expect(list.find((m) => m.id === u2)?.errorCode).toBe("LlmError");
    // El placeholder vacío del turno 2 se descartó.
    expect(list.find((m) => m.id === a2)).toBeUndefined();
  });

  it("onRehydrateStorage baja los estados huérfanos (streaming/sending) a error", async () => {
    // Simulamos un cierre con un stream en vuelo: el storage quedó con un
    // assistant "streaming" (con parcial), un user "done" y otro user "sending".
    const sid = "sess-rehydrate";
    const persisted = {
      state: {
        sessions: { [sid]: { id: sid, mode: "vida", createdAt: 1, updatedAt: 1 } },
        messages: {
          [sid]: [
            { id: "u", role: "user", text: "hola", status: "done" },
            { id: "a", role: "assistant", text: "parci", status: "streaming" },
            { id: "u2", role: "user", text: "otra", status: "sending" },
          ],
        },
      },
      version: 0,
    };
    localStorage.setItem("ynara.chat", JSON.stringify(persisted));
    await useChatStore.persist.rehydrate();

    const list = useChatStore.getState().messages[sid] ?? [];
    expect(list.find((m) => m.id === "a")?.status).toBe("error");
    expect(list.find((m) => m.id === "a")?.text).toBe("parci");
    expect(list.find((m) => m.id === "u2")?.status).toBe("error");
    expect(list.find((m) => m.id === "u")?.status).toBe("done");
  });

  it("onRehydrateStorage descarta un placeholder de assistant vacío en streaming", async () => {
    const sid = "sess-rehydrate-empty";
    const persisted = {
      state: {
        sessions: { [sid]: { id: sid, mode: "vida", createdAt: 1, updatedAt: 1 } },
        messages: {
          [sid]: [
            { id: "u", role: "user", text: "hola", status: "done" },
            { id: "a", role: "assistant", text: "", status: "streaming" },
          ],
        },
      },
      version: 0,
    };
    localStorage.setItem("ynara.chat", JSON.stringify(persisted));
    await useChatStore.persist.rehydrate();

    const list = useChatStore.getState().messages[sid] ?? [];
    expect(list.find((m) => m.id === "a")).toBeUndefined();
    expect(list).toHaveLength(1);
  });

  it("onRehydrateStorage preserva un turno 'degraded' (terminal, no lo baja a error)", async () => {
    const sid = "sess-rehydrate-degraded";
    const persisted = {
      state: {
        sessions: { [sid]: { id: sid, mode: "vida", createdAt: 1, updatedAt: 1 } },
        messages: {
          [sid]: [
            { id: "u", role: "user", text: "hola", status: "done" },
            { id: "a", role: "assistant", text: "", status: "degraded" },
          ],
        },
      },
      version: 0,
    };
    localStorage.setItem("ynara.chat", JSON.stringify(persisted));
    await useChatStore.persist.rehydrate();

    const list = useChatStore.getState().messages[sid] ?? [];
    // 'degraded' es terminal: NO es streaming/sending, así que sobrevive intacto.
    expect(list.find((m) => m.id === "a")?.status).toBe("degraded");
    expect(list).toHaveLength(2);
  });
});
