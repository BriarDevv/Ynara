import { beforeEach, describe, expect, it } from "vitest";
import { createBackendSessionStore } from "./backendSessions";

// Storage en memoria para instanciar el store sin tocar plataforma (mismo patrón
// que completion.test.ts).
function memoryStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => {
      map.set(k, v);
    },
    removeItem: (k: string) => {
      map.delete(k);
    },
  };
}

describe("createBackendSessionStore", () => {
  let store: ReturnType<typeof createBackendSessionStore>;

  beforeEach(() => {
    store = createBackendSessionStore(memoryStorage());
  });

  it("devuelve null para una sesión local sin backendSessionId confirmado", () => {
    expect(store.getState().getBackendSessionId("local-1")).toBeNull();
  });

  it("adopta y devuelve el backendSessionId confirmado por sesión local", () => {
    store.getState().setBackendSessionId("local-1", "backend-1");
    expect(store.getState().getBackendSessionId("local-1")).toBe("backend-1");
    // Otra sesión local sigue sin mapeo (aislamiento por id).
    expect(store.getState().getBackendSessionId("local-2")).toBeNull();
  });

  it("mantiene mapeos independientes por sesión local", () => {
    store.getState().setBackendSessionId("local-1", "backend-1");
    store.getState().setBackendSessionId("local-2", "backend-2");
    expect(store.getState().getBackendSessionId("local-1")).toBe("backend-1");
    expect(store.getState().getBackendSessionId("local-2")).toBe("backend-2");
  });

  it("reset limpia todos los mapeos", () => {
    store.getState().setBackendSessionId("local-1", "backend-1");
    store.getState().reset();
    expect(store.getState().getBackendSessionId("local-1")).toBeNull();
  });

  it("es idempotente: no muta el estado si el id ya coincide", () => {
    store.getState().setBackendSessionId("local-1", "backend-1");
    const stateBefore = store.getState();
    store.getState().setBackendSessionId("local-1", "backend-1");
    // Misma referencia: el guard evita el set (y el re-render que dispararía).
    expect(store.getState()).toBe(stateBefore);
  });
});
