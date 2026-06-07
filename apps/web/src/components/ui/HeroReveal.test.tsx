import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useA11yStore } from "@/stores/a11y";
import { HeroReveal } from "./HeroReveal";

/**
 * `HeroReveal` es el momento-firma GSAP (§16 #7). Mockeamos `@/lib/gsap` con
 * funciones planas que registran en arrays de módulo: nos interesa el **gate**
 * (anima o no según la preferencia de motion) y la query que se le pasa a
 * `matchMedia`, no el tween real. `useGSAP` mockeado corre el callback una vez.
 */
const fromCalls: unknown[][] = [];
const addedQueries: string[] = [];
let revertCount = 0;
// El cleanup que retorna el callback de useGSAP (en runtime lo corre useGSAP al
// revertir el contexto en unmount / cambio de deps). Lo capturamos para probar
// que dispara mm.revert() y no deja el matchMedia colgado.
let capturedCleanup: (() => void) | undefined;

vi.mock("@/lib/gsap", () => ({
  gsap: {
    from: (...args: unknown[]) => {
      fromCalls.push(args);
    },
    matchMedia: () => ({
      add: (query: string, fn: () => void) => {
        addedQueries.push(query);
        fn();
      },
      revert: () => {
        revertCount += 1;
      },
    }),
  },
  useGSAP: (cb: () => unknown) => {
    capturedCleanup = cb() as (() => void) | undefined;
  },
}));

describe("HeroReveal", () => {
  beforeEach(() => {
    fromCalls.length = 0;
    addedQueries.length = 0;
    revertCount = 0;
    capturedCleanup = undefined;
    useA11yStore.setState({ motion: "auto" });
  });

  afterEach(() => {
    useA11yStore.getState().reset();
  });

  it("renderiza los hijos dentro del scope con su className", () => {
    render(
      <HeroReveal className="mi-clase">
        <div data-hero-reveal>hijo</div>
      </HeroReveal>,
    );
    const child = screen.getByText("hijo");
    expect(child).toBeInTheDocument();
    expect(child.parentElement).toHaveClass("mi-clase");
  });

  it("con motion=auto anima [data-hero-reveal] siguiendo el OS-pref", () => {
    render(
      <HeroReveal>
        <div data-hero-reveal>hijo</div>
      </HeroReveal>,
    );
    expect(fromCalls).toHaveLength(1);
    const [firstCall] = fromCalls;
    expect(firstCall?.[0]).toBe("[data-hero-reveal]");
    expect(addedQueries).toContain("(prefers-reduced-motion: no-preference)");
  });

  it("con motion=normal anima siempre (query 'all', ignora el OS)", () => {
    useA11yStore.setState({ motion: "normal" });
    render(
      <HeroReveal>
        <div data-hero-reveal>hijo</div>
      </HeroReveal>,
    );
    expect(fromCalls).toHaveLength(1);
    expect(addedQueries).toContain("all");
  });

  it("bajo motion=reduce no anima (override del store, sin matchMedia)", () => {
    useA11yStore.setState({ motion: "reduce" });
    render(
      <HeroReveal>
        <div data-hero-reveal>hijo</div>
      </HeroReveal>,
    );
    expect(fromCalls).toHaveLength(0);
    expect(addedQueries).toHaveLength(0);
  });

  it("el cleanup revierte el matchMedia (no deja tweens colgados)", () => {
    render(
      <HeroReveal>
        <div data-hero-reveal>hijo</div>
      </HeroReveal>,
    );
    // El callback de useGSAP retornó un cleanup que llama mm.revert().
    expect(capturedCleanup).toBeTypeOf("function");
    expect(revertCount).toBe(0);
    capturedCleanup?.();
    expect(revertCount).toBe(1);
  });
});
