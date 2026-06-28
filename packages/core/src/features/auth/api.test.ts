import { beforeEach, describe, expect, it, vi } from "vitest";

// Mockeamos el cliente HTTP de core para verificar el armado del request de
// logout (endpoint + Bearer + body vacío), no la red.
const post = vi.fn();
vi.mock("../../api", () => ({ api: { post } }));

const { logOut } = await import("./api");

beforeEach(() => {
  post.mockReset();
  post.mockResolvedValue(undefined);
});

describe("logOut", () => {
  it("POST /v1/auth/logout con el Bearer del token y body vacío", async () => {
    await logOut("t1");

    // Bearer explícito (el caller suele resetear el user store en el mismo tick,
    // así que el cliente no puede tomar el token del store). Body vacío: la
    // family-revocation usa el `sid` del access, no manda el refresh token.
    expect(post).toHaveBeenCalledWith(
      "/v1/auth/logout",
      {},
      { headers: { Authorization: "Bearer t1" } },
    );
  });

  it("propaga el throw si el backend falla (el caller lo trata como best-effort)", async () => {
    post.mockRejectedValue(new Error("network"));

    await expect(logOut("t1")).rejects.toThrow();
  });
});
