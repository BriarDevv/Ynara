import { describe, expect, it } from "vitest";

import { UserOutSchema, UserUpdateSchema } from "./user";

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
    onboarding_completed: true,
    retention_sensitive_days: 365,
    created_at: ISO,
    updated_at: ISO,
  };

  it("acepta un UserOut válido", () => {
    expect(UserOutSchema.parse(valid)).toEqual(valid);
  });

  it("rechaza email inválido", () => {
    expect(UserOutSchema.safeParse({ ...valid, email: "no-email" }).success).toBe(false);
  });

  it("rechaza id no-UUID", () => {
    expect(UserOutSchema.safeParse({ ...valid, id: "123" }).success).toBe(false);
  });
});
