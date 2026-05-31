import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useA11yStore } from "@/stores/a11y";
import { useReducedMotion } from "./useReducedMotion";

function mockOSReduced(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

afterEach(() => {
  useA11yStore.getState().reset();
});

describe("useReducedMotion", () => {
  it('motion="reduce" → true, ignora el OS', () => {
    mockOSReduced(false);
    useA11yStore.setState({ motion: "reduce" });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });

  it('motion="normal" → false, gana sobre un OS que pide reduce', () => {
    mockOSReduced(true);
    useA11yStore.setState({ motion: "normal" });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });

  it('motion="auto" → sigue el OS (no reduce)', () => {
    mockOSReduced(false);
    useA11yStore.setState({ motion: "auto" });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });

  it('motion="auto" → sigue el OS (reduce)', () => {
    mockOSReduced(true);
    useA11yStore.setState({ motion: "auto" });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });
});
