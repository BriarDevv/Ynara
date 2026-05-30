import { describe, expect, it } from "vitest";
import type { ModeId } from "@/components/ui/modes";
import { AGENT_MODES, cannedActions, cannedReply, isAgentMode, MODE_INTRO } from "./constants";

const ALL_MODES: ModeId[] = ["productividad", "estudio", "bienestar", "vida", "memoria"];

describe("isAgentMode / AGENT_MODES", () => {
  it("productividad y memoria son modos Qwen (agente)", () => {
    expect(isAgentMode("productividad")).toBe(true);
    expect(isAgentMode("memoria")).toBe(true);
  });

  it("estudio, bienestar y vida son Gemma (no agente)", () => {
    expect(isAgentMode("estudio")).toBe(false);
    expect(isAgentMode("bienestar")).toBe(false);
    expect(isAgentMode("vida")).toBe(false);
  });

  it("AGENT_MODES tiene exactamente los dos modos Qwen", () => {
    expect([...AGENT_MODES].sort()).toEqual(["memoria", "productividad"]);
  });
});

describe("cannedReply", () => {
  it("devuelve una respuesta no vacía para cada modo", () => {
    for (const mode of ALL_MODES) {
      expect(cannedReply(mode, "hola mundo").length).toBeGreaterThan(0);
    }
  });

  it("incluye un eco del texto del usuario", () => {
    expect(cannedReply("vida", "recomendame una serie")).toContain("recomendame una serie");
  });
});

describe("cannedActions", () => {
  it("modos Qwen devuelven actions con result stub", () => {
    for (const mode of AGENT_MODES) {
      const actions = cannedActions(mode);
      expect(actions.length).toBeGreaterThan(0);
      expect(actions[0]?.result).toEqual({ status: "not_wired" });
      expect(actions[0]?.id).toBeTruthy();
      expect(actions[0]?.name).toBeTruthy();
    }
  });

  it("modos Gemma devuelven [] (no ejecutan tools)", () => {
    expect(cannedActions("estudio")).toEqual([]);
    expect(cannedActions("bienestar")).toEqual([]);
    expect(cannedActions("vida")).toEqual([]);
  });
});

describe("MODE_INTRO", () => {
  it("tiene intro para los 5 modos", () => {
    for (const mode of ALL_MODES) {
      expect(MODE_INTRO[mode].length).toBeGreaterThan(0);
    }
  });
});
