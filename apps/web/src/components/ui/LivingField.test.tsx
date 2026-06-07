import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useA11yStore } from "@/stores/a11y";
import { useThemeStore } from "@/stores/theme";
import { LivingField } from "./LivingField";

/**
 * jsdom no implementa canvas 2D: getContext("2d") devuelve null. Para
 * ejercitar el loop completo (rAF + listeners + cleanup) se mockea un
 * contexto donde cada método es un vi.fn() que devuelve otro proxy igual
 * (así `createRadialGradient(...).addColorStop(...)` también funciona).
 */
function createCtxMock(): CanvasRenderingContext2D {
  const handler: ProxyHandler<Record<string | symbol, unknown>> = {
    get(target, prop) {
      if (typeof prop === "symbol") return undefined;
      if (!(prop in target)) {
        target[prop] = vi.fn(() => new Proxy({}, handler));
      }
      return target[prop];
    },
    set(target, prop, value) {
      // fillStyle / strokeStyle / lineWidth: aceptar la asignación.
      target[prop] = value;
      return true;
    },
  };
  return new Proxy({}, handler) as unknown as CanvasRenderingContext2D;
}

/** Eventos que registra el componente — los de React quedan afuera. */
const FIELD_EVENTS = new Set([
  "pointermove",
  "pointerdown",
  "blur",
  "mouseleave",
  "visibilitychange",
  "resize",
]);

type Listener = { target: "window" | "document"; type: string; fn: unknown };

function trackListeners() {
  const added: Listener[] = [];
  const removed: Listener[] = [];
  for (const [target, obj] of [
    ["window", window],
    ["document", document],
  ] as const) {
    const addOriginal = obj.addEventListener.bind(obj);
    const removeOriginal = obj.removeEventListener.bind(obj);
    vi.spyOn(obj, "addEventListener").mockImplementation((type, fn, opts) => {
      if (FIELD_EVENTS.has(type)) added.push({ target, type, fn });
      addOriginal(type, fn as EventListener, opts);
    });
    vi.spyOn(obj, "removeEventListener").mockImplementation((type, fn, opts) => {
      if (FIELD_EVENTS.has(type)) removed.push({ target, type, fn });
      removeOriginal(type, fn as EventListener, opts);
    });
  }
  return { added, removed };
}

describe("LivingField", () => {
  let ctxMock: CanvasRenderingContext2D;
  let rafCallbacks: Map<number, FrameRequestCallback>;
  let rafSpy: ReturnType<typeof vi.fn>;
  let cafSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    ctxMock = createCtxMock();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
      ctxMock as unknown as RenderingContext,
    );
    // rAF determinístico: los frames se disparan a mano con runFrame().
    rafCallbacks = new Map();
    let nextId = 0;
    rafSpy = vi.fn((cb: FrameRequestCallback) => {
      nextId += 1;
      rafCallbacks.set(nextId, cb);
      return nextId;
    });
    cafSpy = vi.fn((id: number) => {
      rafCallbacks.delete(id);
    });
    vi.stubGlobal("requestAnimationFrame", rafSpy);
    vi.stubGlobal("cancelAnimationFrame", cafSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useA11yStore.getState().reset();
    useThemeStore.getState().reset();
    localStorage.clear();
  });

  function runFrame(ts: number) {
    const pending = [...rafCallbacks.values()];
    rafCallbacks.clear();
    for (const cb of pending) cb(ts);
  }

  it("monta un fondo decorativo: aria-hidden, pointer-events-none, -z-10", () => {
    const { container } = render(<LivingField variant="aurora" />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute("aria-hidden");
    expect(wrapper?.className).toContain("pointer-events-none");
    expect(wrapper?.className).toContain("-z-10");
    expect(container.querySelector("canvas")).toBeInTheDocument();
  });

  it("con motion habilitado anima por rAF y limpia TODO al desmontar", () => {
    // motion "normal" fuerza animación sin depender del mock de matchMedia.
    useA11yStore.getState().setMotion("normal");
    const { added, removed } = trackListeners();

    const { unmount } = render(<LivingField variant="aurora" modeId="bienestar" />);

    // El loop arrancó y dibuja frames encadenados.
    expect(rafSpy).toHaveBeenCalled();
    runFrame(16);
    runFrame(32);
    expect(rafCallbacks.size).toBe(1); // siempre un solo frame pendiente

    // aurora es variante con pointer: registró el seguimiento del cursor.
    expect(added.some((l) => l.type === "pointermove")).toBe(true);
    expect(added.some((l) => l.type === "visibilitychange")).toBe(true);

    unmount();

    // El rAF pendiente se canceló…
    expect(cafSpy).toHaveBeenCalled();
    expect(rafCallbacks.size).toBe(0);
    // …y cada listener registrado se removió con la MISMA referencia
    // (si leakea uno, leakea por cada navegación — DESIGN.md §16 #5).
    for (const l of added) {
      expect(
        removed.some((r) => r.target === l.target && r.type === l.type && r.fn === l.fn),
        `listener ${l.target}:${l.type} sin remover`,
      ).toBe(true);
    }
  });

  it("pausa el loop cuando la pestaña se oculta (cero CPU en background)", () => {
    useA11yStore.getState().setMotion("normal");
    const { unmount } = render(<LivingField variant="network" />);
    runFrame(16);
    expect(rafCallbacks.size).toBe(1);

    // El getter vive en Document.prototype (jsdom), no como own property.
    const hidden = vi.spyOn(Document.prototype, "hidden", "get");
    hidden.mockReturnValue(true);
    document.dispatchEvent(new Event("visibilitychange"));
    expect(rafCallbacks.size).toBe(0); // rAF cancelado, nada pendiente

    hidden.mockReturnValue(false);
    document.dispatchEvent(new Event("visibilitychange"));
    expect(rafCallbacks.size).toBe(1); // retoma al volver

    unmount();
    expect(rafCallbacks.size).toBe(0);
  });

  it("con reduce dibuja un único frame estático: sin rAF ni listeners de cursor", () => {
    useA11yStore.getState().setMotion("reduce");
    const { added } = trackListeners();
    const clearRect = ctxMock.clearRect as ReturnType<typeof vi.fn>;

    render(<LivingField variant="aurora" />);

    expect(clearRect).toHaveBeenCalled(); // dibujó (al menos) el frame estático
    expect(rafSpy).not.toHaveBeenCalled(); // pero no arrancó el loop
    expect(added.some((l) => l.type === "pointermove")).toBe(false);
  });

  it("sin contexto 2d (canvas no soportado) no explota ni registra listeners", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const { added } = trackListeners();
    const { unmount } = render(<LivingField variant="constellation" />);
    expect(rafSpy).not.toHaveBeenCalled();
    expect(added).toEqual([]);
    unmount();
  });

  it("monta el canvas y la capa de grano en toda variante con grain > 0", () => {
    const { container } = render(<LivingField variant="paper" />);
    expect(container.querySelector("canvas")).toBeInTheDocument();
    expect(container.querySelector(".field-grain")).toBeInTheDocument();
  });

  it("cambiar el tema re-tiñe pero NO re-randomiza la geometría del campo", () => {
    useA11yStore.getState().setMotion("normal");
    render(<LivingField variant="aurora" />);

    // El init() del montaje ya corrió (randomizó los nodos). Desde acá, el
    // remount del efecto por cambio de color no debe volver a tocar
    // Math.random: la geometría persiste en el snapshot (FieldState) y el
    // campo solo se re-tiñe, sin rebarajarse.
    const randomSpy = vi.spyOn(Math, "random");
    act(() => {
      useThemeStore.getState().setTheme("dark");
    });
    expect(randomSpy).not.toHaveBeenCalled();
  });
});
