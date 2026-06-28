import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useShowReasoningStore } from "./showReasoning";

describe("useShowReasoningStore", () => {
  // jsdom provee localStorage real y el persist de zustand lo usa directo:
  // limpiar entre casos para no dejar residuo (mismo patrón que stores/theme.test.ts).
  beforeEach(() => {
    useShowReasoningStore.getState().reset();
    localStorage.clear();
  });

  afterEach(() => {
    useShowReasoningStore.getState().reset();
    localStorage.clear();
  });

  it("arranca apagado (default OFF: el razonamiento es opt-in)", () => {
    expect(useShowReasoningStore.getState().enabled).toBe(false);
  });

  it("setEnabled prende y apaga", () => {
    useShowReasoningStore.getState().setEnabled(true);
    expect(useShowReasoningStore.getState().enabled).toBe(true);
    useShowReasoningStore.getState().setEnabled(false);
    expect(useShowReasoningStore.getState().enabled).toBe(false);
  });

  it("toggle alterna el estado", () => {
    useShowReasoningStore.getState().toggle();
    expect(useShowReasoningStore.getState().enabled).toBe(true);
    useShowReasoningStore.getState().toggle();
    expect(useShowReasoningStore.getState().enabled).toBe(false);
  });

  it("persiste bajo la key ynara.show-reasoning", () => {
    useShowReasoningStore.getState().setEnabled(true);
    const raw = localStorage.getItem("ynara.show-reasoning");
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw ?? "{}").state.enabled).toBe(true);
  });
});
