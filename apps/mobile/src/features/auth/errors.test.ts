import { ApiError } from "@ynara/core/api";
import { describe, expect, it } from "vitest";
import { authErrorMessage } from "./errors";

describe("authErrorMessage", () => {
  it("401 → credenciales incorrectas (en cualquier modo)", () => {
    expect(authErrorMessage(new ApiError(401, null), "login")).toBe(
      "Email o contraseña incorrectos.",
    );
    expect(authErrorMessage(new ApiError(401, null), "signup")).toBe(
      "Email o contraseña incorrectos.",
    );
  });

  it("409/400 en signup → el email ya existe", () => {
    expect(authErrorMessage(new ApiError(409, null), "signup")).toBe(
      "Ese email ya tiene una cuenta. Iniciá sesión.",
    );
    expect(authErrorMessage(new ApiError(400, null), "signup")).toBe(
      "Ese email ya tiene una cuenta. Iniciá sesión.",
    );
  });

  it("409/400 en login → no pudimos validar", () => {
    expect(authErrorMessage(new ApiError(409, null), "login")).toBe(
      "No pudimos validar tus datos.",
    );
  });

  it("422 → revisá los campos", () => {
    expect(authErrorMessage(new ApiError(422, null), "signup")).toBe(
      "Revisá el email y la contraseña.",
    );
  });

  it("error desconocido / 500 → mensaje genérico", () => {
    expect(authErrorMessage(new Error("boom"), "login")).toBe(
      "Algo no anduvo. Probá de nuevo en un momento.",
    );
    expect(authErrorMessage(new ApiError(500, null), "login")).toBe(
      "Algo no anduvo. Probá de nuevo en un momento.",
    );
  });
});
