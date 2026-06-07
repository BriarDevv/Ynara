import { render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useA11yStore } from "@/stores/a11y";
import { useSmoothScroll } from "./useSmoothScroll";

/**
 * `useSmoothScroll` monta Lenis sobre el contenedor del shell (§16 #7). Mockeamos
 * el módulo `lenis` con una clase que registra construcciones y `destroy()` en
 * arrays de módulo (inmune a clearMocks/restoreMocks) para verificar las dos
 * garantías duras: gate de reduced-motion y cleanup sin leak.
 */
const ctorCalls: Array<{ wrapper: unknown; content: unknown }> = [];
let destroyCount = 0;

vi.mock("lenis", () => ({
  default: class MockLenis {
    constructor(opts: { wrapper: unknown; content: unknown }) {
      ctorCalls.push({ wrapper: opts.wrapper, content: opts.content });
    }
    destroy() {
      destroyCount += 1;
    }
  },
}));

// El shell vive en una sola ruta durante el test; lo que importa es que el
// hook lo tenga en deps (recrear por navegación), no el valor.
vi.mock("next/navigation", () => ({ usePathname: () => "/hoy" }));

function Harness() {
  const ref = useRef<HTMLDivElement>(null);
  useSmoothScroll(ref);
  return (
    <div ref={ref} data-testid="wrapper">
      <div data-testid="content">contenido</div>
    </div>
  );
}

describe("useSmoothScroll", () => {
  beforeEach(() => {
    ctorCalls.length = 0;
    destroyCount = 0;
    useA11yStore.setState({ motion: "auto" });
  });

  afterEach(() => {
    useA11yStore.getState().reset();
  });

  it("monta Lenis sobre el wrapper, con el hijo directo como content", () => {
    const { getByTestId } = render(<Harness />);
    expect(ctorCalls).toHaveLength(1);
    const [call] = ctorCalls;
    expect(call?.wrapper).toBe(getByTestId("wrapper"));
    expect(call?.content).toBe(getByTestId("content"));
  });

  it("bajo reduced-motion no instancia Lenis (scroll nativo)", () => {
    useA11yStore.setState({ motion: "reduce" });
    render(<Harness />);
    expect(ctorCalls).toHaveLength(0);
  });

  it("destruye la instancia al desmontar (sin leak de rAF/listeners)", () => {
    const { unmount } = render(<Harness />);
    expect(destroyCount).toBe(0);
    unmount();
    expect(destroyCount).toBe(1);
  });
});
