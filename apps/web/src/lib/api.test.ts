import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useUserStore } from "@/stores/user";
import { api } from "./api";

// Mock de fetch que devuelve un JSON 200 y captura los headers del request.
function mockFetch() {
  return vi.fn(async (..._args: unknown[]) => ({
    ok: true,
    status: 200,
    headers: {
      get: (k: string) => (k.toLowerCase() === "content-type" ? "application/json" : null),
    },
    json: async () => ({ ok: true }),
    text: async () => "",
  }));
}

function authHeaderOf(fetchMock: ReturnType<typeof mockFetch>): string | null {
  const init = fetchMock.mock.calls[0]?.[1] as { headers: Headers } | undefined;
  return init?.headers.get("Authorization") ?? null;
}

describe("api — inyección de auth (Bearer)", () => {
  let fetchMock: ReturnType<typeof mockFetch>;

  beforeEach(() => {
    useUserStore.getState().reset();
    fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useUserStore.getState().reset();
  });

  it("adjunta Authorization: Bearer cuando hay token en el store", async () => {
    useUserStore.getState().setAuth({ userId: "u1", token: "tok-123", isEphemeral: false });
    await api.get("/v1/sessions");
    expect(authHeaderOf(fetchMock)).toBe("Bearer tok-123");
  });

  it("no adjunta Authorization si no hay token", async () => {
    await api.get("/v1/health");
    expect(authHeaderOf(fetchMock)).toBeNull();
  });

  it("respeta skipAuth aunque haya token (endpoints públicos)", async () => {
    useUserStore.getState().setAuth({ userId: "u1", token: "tok-123", isEphemeral: false });
    await api.post("/v1/auth/token", { email: "a@b.com" }, { skipAuth: true });
    expect(authHeaderOf(fetchMock)).toBeNull();
  });

  it("NO manda el Bearer a un host ajeno (perímetro)", async () => {
    useUserStore.getState().setAuth({ userId: "u1", token: "tok-123", isEphemeral: false });
    await api.get("https://evil.example.com/steal");
    expect(authHeaderOf(fetchMock)).toBeNull();
  });
});
