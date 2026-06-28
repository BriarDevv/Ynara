import { describe, expect, it } from "vitest";

import { AboutYouSchema, OnboardingIntakeSchema, UserOutSchema, UserUpdateSchema } from "./user";

const ISO = "2026-05-08T09:42:00+00:00";
const UUID = "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

describe("UserUpdateSchema", () => {
  it("acepta un update parcial (solo display_name)", () => {
    expect(UserUpdateSchema.parse({ display_name: "Mateo" })).toEqual({ display_name: "Mateo" });
  });

  it("acepta un body vacío (no-op idempotente)", () => {
    expect(UserUpdateSchema.parse({})).toEqual({});
  });

  it("acepta retention en rango + onboarding_completed", () => {
    expect(
      UserUpdateSchema.parse({ retention_sensitive_days: 90, onboarding_completed: true }),
    ).toEqual({ retention_sensitive_days: 90, onboarding_completed: true });
  });

  it("rechaza retention fuera de 30..365", () => {
    expect(UserUpdateSchema.safeParse({ retention_sensitive_days: 10 }).success).toBe(false);
    expect(UserUpdateSchema.safeParse({ retention_sensitive_days: 400 }).success).toBe(false);
  });

  it("rechaza display_name inválido (muy corto)", () => {
    expect(UserUpdateSchema.safeParse({ display_name: "M" }).success).toBe(false);
  });
});

describe("UserOutSchema", () => {
  const valid = {
    id: UUID,
    email: "mateo@example.com",
    display_name: "Mateo",
    is_ephemeral: false,
    onboarding_completed: true,
    time_zone: "UTC",
    retention_sensitive_days: 365,
    preferences: {
      interested_modes: ["productividad", "estudio"],
      a11y: { text_size: "md", high_contrast: false, motion: "auto" },
    },
    created_at: ISO,
    updated_at: ISO,
  };

  it("acepta un UserOut válido con preferences pobladas", () => {
    expect(UserOutSchema.parse(valid)).toEqual(valid);
  });

  it("default is_ephemeral=false y time_zone=UTC cuando faltan (defensivo)", () => {
    const { is_ephemeral: _e, time_zone: _t, ...rest } = valid;
    const parsed = UserOutSchema.parse(rest);
    expect(parsed.is_ephemeral).toBe(false);
    expect(parsed.time_zone).toBe("UTC");
  });

  it("default preferences a {} cuando la clave falta (defensivo)", () => {
    const { preferences: _omit, ...rest } = valid;
    expect(UserOutSchema.parse(rest).preferences).toEqual({});
  });

  it("acepta preferences vacío (filas pre-onboarding)", () => {
    expect(UserOutSchema.parse({ ...valid, preferences: {} }).preferences).toEqual({});
  });

  it("rechaza un modo inválido en preferences.interested_modes", () => {
    expect(
      UserOutSchema.safeParse({ ...valid, preferences: { interested_modes: ["nope"] } }).success,
    ).toBe(false);
  });

  it("rechaza email inválido", () => {
    expect(UserOutSchema.safeParse({ ...valid, email: "no-email" }).success).toBe(false);
  });

  it("rechaza id no-UUID", () => {
    expect(UserOutSchema.safeParse({ ...valid, id: "123" }).success).toBe(false);
  });
});

describe("AboutYouSchema", () => {
  const valid = {
    dedication: "ambos",
    studyWhat: "ingenieria",
    workWhat: "freelance",
    purpose: "organizarme",
    interests: "musica",
  };

  it("acepta un about completo", () => {
    expect(AboutYouSchema.parse(valid)).toEqual(valid);
  });

  it("acepta dedication null + free-text vacío (sobre-vos en blanco)", () => {
    const blank = {
      dedication: null,
      studyWhat: "",
      workWhat: "",
      purpose: "",
      interests: "",
    };
    expect(AboutYouSchema.parse(blank)).toEqual(blank);
  });

  it("rechaza dedication fuera del enum", () => {
    expect(AboutYouSchema.safeParse({ ...valid, dedication: "vacaciones" }).success).toBe(false);
  });

  it("rechaza free-text > 200 (anti-inflado del body)", () => {
    expect(AboutYouSchema.safeParse({ ...valid, purpose: "a".repeat(201) }).success).toBe(false);
  });
});

describe("OnboardingIntakeSchema", () => {
  const valid = {
    displayName: "Mateo",
    mood: ["tranquilo"],
    moodFreeText: "arrancando",
    interestedModes: ["productividad", "estudio"],
    a11y: { textSize: "md", highContrast: false, motion: "auto" },
    about: {
      dedication: "estudio",
      studyWhat: "ingenieria",
      workWhat: "",
      purpose: "organizarme",
      interests: "running",
    },
  };

  it("acepta un intake completo", () => {
    expect(OnboardingIntakeSchema.safeParse(valid).success).toBe(true);
  });

  it("acepta about null (sobre-vos saltado) y moodFreeText ausente", () => {
    const { moodFreeText: _omit, ...rest } = valid;
    expect(OnboardingIntakeSchema.safeParse({ ...rest, about: null }).success).toBe(true);
  });

  it("rechaza interestedModes vacío (gate del step modos)", () => {
    expect(OnboardingIntakeSchema.safeParse({ ...valid, interestedModes: [] }).success).toBe(false);
  });

  it("rechaza un modo inexistente", () => {
    expect(
      OnboardingIntakeSchema.safeParse({ ...valid, interestedModes: ["inventado"] }).success,
    ).toBe(false);
  });
});
