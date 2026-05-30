import { describe, expect, it } from "vitest";
import {
  MAX_MOOD_FREE_TEXT,
  MAX_MOODS,
  ModesFormSchema,
  MoodFormSchema,
  NameFormSchema,
} from "./schemas";

describe("MoodFormSchema", () => {
  it("acepta un array de moods vacío (el step es opcional, sin mínimo)", () => {
    const result = MoodFormSchema.safeParse({ mood: [], moodFreeText: "" });
    expect(result.success).toBe(true);
  });

  it("acepta hasta MAX_MOODS moods", () => {
    const result = MoodFormSchema.safeParse({
      mood: ["tranquilo", "creativo"],
      moodFreeText: "todo bien",
    });
    expect(result.success).toBe(true);
  });

  it(`rechaza más de ${MAX_MOODS} moods`, () => {
    const result = MoodFormSchema.safeParse({
      mood: ["tranquilo", "creativo", "cansado"],
      moodFreeText: "",
    });
    expect(result.success).toBe(false);
  });

  it("acepta el texto libre justo en el límite de caracteres", () => {
    const result = MoodFormSchema.safeParse({
      mood: [],
      moodFreeText: "a".repeat(MAX_MOOD_FREE_TEXT),
    });
    expect(result.success).toBe(true);
  });

  it("rechaza el texto libre por encima del límite de caracteres", () => {
    const result = MoodFormSchema.safeParse({
      mood: [],
      moodFreeText: "a".repeat(MAX_MOOD_FREE_TEXT + 1),
    });
    expect(result.success).toBe(false);
  });
});

describe("ModesFormSchema", () => {
  it("acepta al menos un modo válido", () => {
    const result = ModesFormSchema.safeParse({ interestedModes: ["productividad"] });
    expect(result.success).toBe(true);
  });

  it('rechaza el array vacío con el mensaje "Elegí al menos uno"', () => {
    const result = ModesFormSchema.safeParse({ interestedModes: [] });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("Elegí al menos uno");
    }
  });

  it("rechaza un modo que no existe en el enum", () => {
    const result = ModesFormSchema.safeParse({ interestedModes: ["inexistente"] });
    expect(result.success).toBe(false);
  });
});

describe("NameFormSchema", () => {
  it("acepta un nombre válido", () => {
    const result = NameFormSchema.safeParse({ displayName: "Mateo" });
    expect(result.success).toBe(true);
  });

  it("rechaza un nombre demasiado corto", () => {
    const result = NameFormSchema.safeParse({ displayName: "M" });
    expect(result.success).toBe(false);
  });

  it("rechaza un nombre con caracteres no permitidos", () => {
    const result = NameFormSchema.safeParse({ displayName: "Mateo123" });
    expect(result.success).toBe(false);
  });
});
