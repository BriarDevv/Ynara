import { describe, expect, it } from "vitest";
import {
  A11yPrefsSchema,
  ApiErrorBodySchema,
  AuthResponseSchema,
  DisplayNameSchema,
  LoginRequestSchema,
  ModeSchema,
  NameFormSchema,
  OnboardRequestSchema,
  SignupRequestSchema,
} from "./schemas";

// Los Zod compartidos con backend viven en @ynara/shared-schemas; el barrel
// de features/onboarding los re-exporta para mantener una sola importación
// desde la UI. Los tests del onboarding cubren:
//   1) NameFormSchema (lo único nuevo definido acá).
//   2) Smoke check de los re-exports — que estén disponibles y sean Zod
//      schemas operativos (.safeParse existe).

describe("NameFormSchema", () => {
  it("acepta un nombre válido", () => {
    const result = NameFormSchema.safeParse({ displayName: "Mateo" });
    expect(result.success).toBe(true);
  });

  it("acepta nombres con acentos y eñes", () => {
    expect(NameFormSchema.safeParse({ displayName: "José" }).success).toBe(true);
    expect(NameFormSchema.safeParse({ displayName: "Begoña" }).success).toBe(true);
    expect(NameFormSchema.safeParse({ displayName: "María Luján" }).success).toBe(true);
  });

  it("acepta apóstrofes y guiones (nombres compuestos)", () => {
    expect(NameFormSchema.safeParse({ displayName: "O'Brien" }).success).toBe(true);
    expect(NameFormSchema.safeParse({ displayName: "Jean-Pierre" }).success).toBe(true);
  });

  it("trimea espacios antes de validar", () => {
    const result = NameFormSchema.safeParse({ displayName: "  Mateo  " });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.displayName).toBe("Mateo");
    }
  });

  it("rechaza menos de 2 caracteres", () => {
    expect(NameFormSchema.safeParse({ displayName: "" }).success).toBe(false);
    expect(NameFormSchema.safeParse({ displayName: "M" }).success).toBe(false);
    expect(NameFormSchema.safeParse({ displayName: "   " }).success).toBe(false);
  });

  it("rechaza más de 40 caracteres", () => {
    const tooLong = "A".repeat(41);
    expect(NameFormSchema.safeParse({ displayName: tooLong }).success).toBe(false);
  });

  it("acepta exactamente 40 caracteres (límite superior incluido)", () => {
    const justRight = "A".repeat(40);
    expect(NameFormSchema.safeParse({ displayName: justRight }).success).toBe(true);
  });

  it("rechaza dígitos y símbolos no permitidos", () => {
    expect(NameFormSchema.safeParse({ displayName: "Mateo123" }).success).toBe(false);
    expect(NameFormSchema.safeParse({ displayName: "Mateo@" }).success).toBe(false);
    expect(NameFormSchema.safeParse({ displayName: "M_ateo" }).success).toBe(false);
  });

  it("rechaza displayName ausente", () => {
    expect(NameFormSchema.safeParse({}).success).toBe(false);
  });
});

describe("Re-exports del barrel", () => {
  it("expone los schemas de @ynara/shared-schemas con .safeParse operativo", () => {
    // Smoke: cada re-export debe ser un objeto con `.safeParse`. Si el
    // re-export se rompe (typo, mal path), este test cae primero.
    for (const schema of [
      A11yPrefsSchema,
      ApiErrorBodySchema,
      AuthResponseSchema,
      DisplayNameSchema,
      LoginRequestSchema,
      ModeSchema,
      OnboardRequestSchema,
      SignupRequestSchema,
    ]) {
      expect(typeof schema.safeParse).toBe("function");
    }
  });

  it("A11yPrefsSchema acepta una preferencia válida", () => {
    const result = A11yPrefsSchema.safeParse({
      textSize: "md",
      highContrast: false,
      motion: "auto",
    });
    expect(result.success).toBe(true);
  });

  it("A11yPrefsSchema rechaza textSize fuera del enum", () => {
    const result = A11yPrefsSchema.safeParse({
      textSize: "xl",
      highContrast: false,
      motion: "auto",
    });
    expect(result.success).toBe(false);
  });

  it("ModeSchema rechaza un modo inexistente", () => {
    expect(ModeSchema.safeParse("inventado").success).toBe(false);
  });
});
