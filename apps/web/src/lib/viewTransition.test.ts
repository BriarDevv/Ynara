import { afterEach, describe, expect, it, vi } from "vitest";
import { startViewTransition } from "./viewTransition";

// jsdom no tiene startViewTransition. Lo agregamos/quitamos vía un cast a
// un tipo donde es opcional (el DOM lib la tipa como requerida → choca).
const doc = document as unknown as { startViewTransition?: (cb: () => void) => unknown };

afterEach(() => {
  delete doc.startViewTransition;
  document.documentElement.className = "";
});

describe("startViewTransition", () => {
  it("sin soporte de la API → corre update directo", () => {
    const update = vi.fn();
    startViewTransition(update);
    expect(update).toHaveBeenCalledTimes(1);
  });

  it("con soporte → usa la API", () => {
    const api = vi.fn((cb: () => void) => cb());
    doc.startViewTransition = api;
    const update = vi.fn();
    startViewTransition(update);
    expect(api).toHaveBeenCalledTimes(1);
    expect(update).toHaveBeenCalledTimes(1);
  });

  it("con soporte pero motion-off → corre directo, sin la API", () => {
    const api = vi.fn((cb: () => void) => cb());
    doc.startViewTransition = api;
    document.documentElement.classList.add("motion-off");
    const update = vi.fn();
    startViewTransition(update);
    expect(api).not.toHaveBeenCalled();
    expect(update).toHaveBeenCalledTimes(1);
  });
});
