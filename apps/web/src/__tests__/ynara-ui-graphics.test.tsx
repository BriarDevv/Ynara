// Verificación del sistema gráfico "Red de memoria" de @ynara/ui
// (DESIGN.md §2 / §3.6, F0.3). Vive en apps/web por el stack RTL+jsdom y
// ejercita el wiring de @ynara/ui desde un consumidor real.
import { render } from "@testing-library/react";
import { buildMemoryField, GrainOverlay, MemoryField } from "@ynara/ui";
import { describe, expect, it } from "vitest";

describe("@ynara/ui · buildMemoryField (geometría)", () => {
  it("es determinista: mismo density+seed → misma red", () => {
    expect(buildMemoryField("media", 7)).toStrictEqual(buildMemoryField("media", 7));
  });

  it("seeds distintos dan layouts distintos", () => {
    expect(buildMemoryField("media", 7)).not.toStrictEqual(buildMemoryField("media", 99));
  });

  it("más densidad → más nodos (5×3 / 7×4 / 9×6)", () => {
    expect(buildMemoryField("dispersa", 1).nodes).toHaveLength(15);
    expect(buildMemoryField("media", 1).nodes).toHaveLength(28);
    expect(buildMemoryField("densa", 1).nodes).toHaveLength(54);
  });

  it("no usa Math.random (estable para SSR): no depende del orden de llamada", () => {
    const a = buildMemoryField("media", 42);
    void buildMemoryField("densa", 1);
    expect(buildMemoryField("media", 42)).toStrictEqual(a);
  });
});

describe("@ynara/ui · MemoryField (render)", () => {
  it("renderiza un <svg> decorativo que llena el contenedor", () => {
    const { container } = render(<MemoryField />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(svg?.getAttribute("width")).toBe("100%");
    expect(svg?.getAttribute("preserveAspectRatio")).toBe("xMidYMid slice");
    expect(svg?.querySelectorAll("path, circle").length ?? 0).toBeGreaterThan(0);
  });

  it("colorea por tokens de la rampa de memoria, nunca hex", () => {
    const { container } = render(<MemoryField variant="nocturna" />);
    const html = container.innerHTML;
    expect(html).toContain("var(--color-memory");
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });
});

describe("@ynara/ui · GrainOverlay (render)", () => {
  it("renderiza una capa decorativa que envuelve .bg-grain", () => {
    const { container } = render(<GrainOverlay />);
    const layer = container.firstElementChild as HTMLElement | null;
    expect(layer?.tagName).toBe("DIV");
    expect(layer?.getAttribute("aria-hidden")).toBe("true");
    expect(layer?.className).toContain("bg-grain");
    expect(layer?.style.position).toBe("absolute");
    expect(layer?.style.pointerEvents).toBe("none");
  });
});
