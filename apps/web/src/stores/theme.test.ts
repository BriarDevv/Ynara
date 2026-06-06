import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { applyThemeClass, useThemeStore } from "./theme";

describe("useThemeStore", () => {
  // jsdom provee localStorage real y el persist de zustand lo usa directo:
  // limpiar entre casos para no dejar residuo a otros archivos de test
  // (mismo patrón que features/chat/store.test.ts).
  beforeEach(() => {
    useThemeStore.getState().reset();
    localStorage.clear();
  });

  afterEach(() => {
    useThemeStore.getState().reset();
    localStorage.clear();
    document.documentElement.classList.remove("theme-dark");
    delete document.documentElement.dataset.theme;
  });

  it("arranca en claro (default de marca, §3.1)", () => {
    expect(useThemeStore.getState().theme).toBe("light");
  });

  it("setTheme cambia el tema", () => {
    useThemeStore.getState().setTheme("dark");
    expect(useThemeStore.getState().theme).toBe("dark");
  });

  it("toggleTheme alterna claro ↔ Noche", () => {
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().theme).toBe("dark");
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().theme).toBe("light");
  });

  it("persiste bajo la key ynara.theme", () => {
    useThemeStore.getState().setTheme("dark");
    const raw = localStorage.getItem("ynara.theme");
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw ?? "{}").state.theme).toBe("dark");
  });
});

describe("applyThemeClass", () => {
  afterEach(() => {
    document.documentElement.classList.remove("theme-dark");
    delete document.documentElement.dataset.theme;
  });

  it("dark agrega html.theme-dark y data-theme", () => {
    applyThemeClass({ theme: "dark" });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("light quita html.theme-dark y vuelve data-theme a light", () => {
    applyThemeClass({ theme: "dark" });
    applyThemeClass({ theme: "light" });
    expect(document.documentElement.classList.contains("theme-dark")).toBe(false);
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
