import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, type Mock, vi } from "vitest";
import { isNearBottom, NEAR_BOTTOM_THRESHOLD, useChatAutoScroll } from "./useChatAutoScroll";

// `useReducedMotion` mockeado para ejercer las dos ramas del salto (smooth/auto)
// sin depender del matchMedia real. Default: no-reduce (smooth).
const { reducedMock } = vi.hoisted(() => ({ reducedMock: vi.fn(() => false) }));
vi.mock("@/hooks/useReducedMotion", () => ({
  useReducedMotion: () => reducedMock(),
}));

afterEach(() => {
  reducedMock.mockReturnValue(false);
  vi.restoreAllMocks();
});

/** Scroller falso (jsdom no tiene layout): controla las métricas a mano. */
function fakeScroller(over: Partial<Record<string, unknown>> = {}): HTMLElement {
  return {
    scrollHeight: 500,
    scrollTop: 0,
    clientHeight: 100,
    scrollTo: vi.fn(),
    focus: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    ...over,
  } as unknown as HTMLElement;
}

describe("isNearBottom", () => {
  it("es true pegado al fondo (gap 0)", () => {
    expect(isNearBottom(1000, 900, 100)).toBe(true); // 1000-900-100 = 0
  });

  it("es true dentro del umbral", () => {
    // gap = 1000 - 820 - 100 = 80 <= 96
    expect(isNearBottom(1000, 820, 100)).toBe(true);
  });

  it("es true justo en el umbral (límite inclusivo)", () => {
    // gap = 1000 - 804 - 100 = 96 <= 96
    expect(isNearBottom(1000, 804, 100)).toBe(true);
  });

  it("es false más allá del umbral", () => {
    // gap = 1000 - 700 - 100 = 200 > 96
    expect(isNearBottom(1000, 700, 100)).toBe(false);
  });

  it("trata el over-scroll (gap negativo) como pegado al fondo", () => {
    // gap = 1000 - 950 - 100 = -50 <= 96 (rubber-band / elastic scroll)
    expect(isNearBottom(1000, 950, 100)).toBe(true);
  });

  it("respeta un umbral custom", () => {
    expect(isNearBottom(1000, 700, 100, 200)).toBe(true); // gap 200 <= 200
    expect(isNearBottom(1000, 700, 100, 199)).toBe(false); // gap 200 > 199
  });

  it("expone el umbral por default", () => {
    expect(NEAR_BOTTOM_THRESHOLD).toBe(96);
  });
});

describe("useChatAutoScroll", () => {
  it("arranca sin botón y jumpToBottom es no-op con ref null", () => {
    const ref = { current: null };
    const { result } = renderHook(() => useChatAutoScroll(ref, "k0"));
    expect(result.current.showJumpButton).toBe(false);
    // No debe tirar aunque no haya scroller montado.
    expect(() => act(() => result.current.jumpToBottom())).not.toThrow();
  });

  it("jumpToBottom scrollea al fondo (smooth), enfoca el scroller y oculta el botón", () => {
    const el = fakeScroller();
    const ref = { current: el };

    const { result } = renderHook(() => useChatAutoScroll(ref, "k1"));
    act(() => result.current.jumpToBottom());

    const lastCall = (el.scrollTo as Mock).mock.lastCall?.[0];
    expect(lastCall).toMatchObject({ top: 500, behavior: "smooth" });
    expect(el.focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(result.current.showJumpButton).toBe(false);
  });

  it("bajo reduced-motion el salto es instantáneo (behavior auto)", () => {
    reducedMock.mockReturnValue(true);
    const el = fakeScroller();

    const { result } = renderHook(() => useChatAutoScroll({ current: el }, "k2"));
    act(() => result.current.jumpToBottom());

    const lastCall = (el.scrollTo as Mock).mock.lastCall?.[0];
    expect(lastCall).toMatchObject({ behavior: "auto" });
  });
});
