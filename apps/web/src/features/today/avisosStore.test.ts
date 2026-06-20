import { beforeEach, describe, expect, it } from "vitest";
import { useAvisosStore } from "./avisosStore";

beforeEach(() => {
  useAvisosStore.getState().reset();
});

describe("useAvisosStore", () => {
  it("resolve marca un aviso como resuelto (idempotente)", () => {
    useAvisosStore.getState().resolve("a");
    expect(useAvisosStore.getState().resolvedIds.has("a")).toBe(true);
    useAvisosStore.getState().resolve("a");
    expect(useAvisosStore.getState().resolvedIds.size).toBe(1);
  });

  it("acumula varios avisos resueltos", () => {
    useAvisosStore.getState().resolve("a");
    useAvisosStore.getState().resolve("b");
    expect(useAvisosStore.getState().resolvedIds.size).toBe(2);
  });

  it("reset limpia el set (lo usa el logout-total)", () => {
    useAvisosStore.getState().resolve("a");
    useAvisosStore.getState().reset();
    expect(useAvisosStore.getState().resolvedIds.size).toBe(0);
  });
});
