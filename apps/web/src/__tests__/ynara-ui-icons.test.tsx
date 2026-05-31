// Verificación del set de íconos de @ynara/ui (DESIGN.md §9, F0.2).
// Vive en apps/web porque acá está el stack de tests (RTL + jsdom) y de
// paso ejercita el wiring de @ynara/ui desde un consumidor real (F0.0).
import { render } from "@testing-library/react";
import { ICON_NAMES, Icon } from "@ynara/ui";
import { describe, expect, it } from "vitest";

describe("@ynara/ui · set de íconos", () => {
  it("expone los 15 íconos del set (10 de marca + 5 utilitarios)", () => {
    expect(ICON_NAMES).toHaveLength(15);
  });

  it("renderiza cada ícono como un <svg> de trazo uniforme con geometría", () => {
    for (const name of ICON_NAMES) {
      const { container, unmount } = render(<Icon name={name} />);
      const svg = container.querySelector("svg");
      expect(svg, name).not.toBeNull();
      // Trazo, nunca relleno (el "trazo uniforme" del §9).
      expect(svg?.getAttribute("fill")).toBe("none");
      expect(svg?.getAttribute("stroke")).toBe("currentColor");
      expect(svg?.getAttribute("stroke-linecap")).toBe("round");
      // Cada ícono tiene al menos una primitiva dibujada.
      expect(svg?.querySelectorAll("circle, rect, path").length ?? 0).toBeGreaterThan(0);
      unmount();
    }
  });

  it("es decorativo por defecto y accesible cuando se le pasa title", () => {
    const { container, rerender } = render(<Icon name="enviar" />);
    const decorative = container.querySelector("svg");
    expect(decorative?.getAttribute("aria-hidden")).toBe("true");
    expect(decorative?.getAttribute("role")).toBeNull();

    rerender(<Icon name="enviar" title="Enviar" />);
    const labeled = container.querySelector("svg");
    expect(labeled?.getAttribute("role")).toBe("img");
    expect(labeled?.getAttribute("aria-label")).toBe("Enviar");
    expect(labeled?.getAttribute("aria-hidden")).toBeNull();
  });

  it("respeta size y strokeWidth custom sin romper el viewBox", () => {
    const { container } = render(<Icon name="foco" size={40} strokeWidth={1.5} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("40");
    expect(svg?.getAttribute("viewBox")).toBe("0 0 44 44");
    expect(svg?.getAttribute("stroke-width")).toBe("1.5");
  });
});
