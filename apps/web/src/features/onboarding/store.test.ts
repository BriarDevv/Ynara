import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useOnboardingStore } from "./store";

/**
 * Tests del store del draft de onboarding. El store es un singleton de
 * Zustand: lo reseteamos antes y después de cada test para que el orden
 * de ejecución no acople. Operamos vía `getState()` (sin React).
 */
const { getState, setState } = useOnboardingStore;
const initial = { ...getState() };

beforeEach(() => {
  getState().reset();
});

afterEach(() => {
  setState(initial, true);
});

describe("useOnboardingStore", () => {
  it("arranca con el estado inicial (auth, sin auth, listas vacías)", () => {
    const s = getState();
    expect(s.currentStep).toBe("auth");
    expect(s.authedUserId).toBeNull();
    expect(s.authedToken).toBeNull();
    expect(s.authMode).toBeNull();
    expect(s.displayName).toBe("");
    expect(s.mood).toEqual([]);
    expect(s.moodFreeText).toBe("");
    expect(s.interestedModes).toEqual([]);
  });

  it("setStep actualiza el step actual", () => {
    getState().setStep("modos");
    expect(getState().currentStep).toBe("modos");
  });

  it("setAuth guarda userId, token y modo juntos", () => {
    getState().setAuth({ userId: "u-1", token: "t-1", mode: "signup" });
    const s = getState();
    expect(s.authedUserId).toBe("u-1");
    expect(s.authedToken).toBe("t-1");
    expect(s.authMode).toBe("signup");
  });

  it("setDisplayName guarda el nombre", () => {
    getState().setDisplayName("Mateo");
    expect(getState().displayName).toBe("Mateo");
  });

  it("setMood guarda moods y texto libre", () => {
    getState().setMood(["tranquilo", "creativo"], "vengo bien");
    const s = getState();
    expect(s.mood).toEqual(["tranquilo", "creativo"]);
    expect(s.moodFreeText).toBe("vengo bien");
  });

  it("setInterestedModes guarda los modos elegidos", () => {
    getState().setInterestedModes(["productividad", "estudio"]);
    expect(getState().interestedModes).toEqual(["productividad", "estudio"]);
  });

  it("reset vuelve todo al estado inicial tras varios cambios", () => {
    const s = getState();
    s.setAuth({ userId: "u-1", token: "t-1", mode: "login" });
    s.setDisplayName("Mateo");
    s.setMood(["estresado"], "uf");
    s.setInterestedModes(["bienestar"]);
    s.setStep("a11y");

    getState().reset();

    const after = getState();
    expect(after.currentStep).toBe("auth");
    expect(after.authedUserId).toBeNull();
    expect(after.authMode).toBeNull();
    expect(after.displayName).toBe("");
    expect(after.mood).toEqual([]);
    expect(after.moodFreeText).toBe("");
    expect(after.interestedModes).toEqual([]);
  });
});
