import { beforeEach, describe, expect, it } from "vitest";
import { useBackendSessionStore } from "./backendSessions";

beforeEach(() => {
  useBackendSessionStore.getState().reset();
  localStorage.clear();
});

describe("useBackendSessionStore", () => {
  it("devuelve null para una sesión local sin backendSessionId confirmado", () => {
    expect(useBackendSessionStore.getState().getBackendSessionId("local-1")).toBeNull();
  });

  it("adopta y devuelve el backendSessionId confirmado por sesión local", () => {
    useBackendSessionStore.getState().setBackendSessionId("local-1", "backend-1");
    expect(useBackendSessionStore.getState().getBackendSessionId("local-1")).toBe("backend-1");
    // Otra sesión local sigue sin mapeo (aislamiento por id).
    expect(useBackendSessionStore.getState().getBackendSessionId("local-2")).toBeNull();
  });

  it("mantiene mapeos independientes por sesión local", () => {
    useBackendSessionStore.getState().setBackendSessionId("local-1", "backend-1");
    useBackendSessionStore.getState().setBackendSessionId("local-2", "backend-2");
    expect(useBackendSessionStore.getState().getBackendSessionId("local-1")).toBe("backend-1");
    expect(useBackendSessionStore.getState().getBackendSessionId("local-2")).toBe("backend-2");
  });

  it("reset limpia todos los mapeos", () => {
    useBackendSessionStore.getState().setBackendSessionId("local-1", "backend-1");
    useBackendSessionStore.getState().reset();
    expect(useBackendSessionStore.getState().getBackendSessionId("local-1")).toBeNull();
  });
});
