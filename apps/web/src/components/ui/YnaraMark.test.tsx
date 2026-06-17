import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { YnaraMark } from "./YnaraMark";

describe("YnaraMark", () => {
  it("es accesible: role=img + aria-label", () => {
    const { getByRole } = render(<YnaraMark />);
    expect(getByRole("img", { name: "Ynara" })).toBeInTheDocument();
  });

  it("respeta size y title", () => {
    const { getByRole } = render(<YnaraMark size={48} title="Ir a Hoy" />);
    const svg = getByRole("img", { name: "Ir a Hoy" });
    expect(svg).toHaveAttribute("width", "48");
    expect(svg).toHaveAttribute("height", "48");
  });

  it("la variante color usa los gradientes oficiales del isotipo", () => {
    const { container } = render(<YnaraMark variant="color" />);
    const html = container.innerHTML;
    // Los 3 gradientes oficiales (diamante violeta, forma azul, relieve).
    expect(container.querySelectorAll("linearGradient").length).toBeGreaterThanOrEqual(3);
    expect(html).toContain("#305ba6"); // azul oficial de la forma
    expect(html).toContain("#8265a3"); // violeta del diamante
    // Y no quedó ningún stop legacy fuera de paleta.
    expect(html).not.toContain("blue-base");
    expect(html).not.toContain("#1f66db");
  });

  it("las variantes mono son silueta plana, sin gradientes", () => {
    for (const [variant, token] of [
      ["mono-dark", "var(--color-noche"],
      ["mono-light", "var(--color-marfil"],
    ] as const) {
      const { container } = render(<YnaraMark variant={variant} />);
      const html = container.innerHTML;
      expect(html).toContain(token);
      expect(html).not.toContain("linearGradient");
      expect(html.toLowerCase()).not.toContain("url(#");
    }
  });

  it("avatar es un cuadrado redondeado con el símbolo oficial a color", () => {
    const { container } = render(<YnaraMark variant="avatar" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("viewBox", "0 0 1012.54 1009.81");
    const rect = container.querySelector("rect");
    expect(rect).toHaveAttribute("rx", "175.55");
    // Símbolo a color → gradientes oficiales presentes.
    expect(container.querySelectorAll("linearGradient").length).toBeGreaterThanOrEqual(3);
  });

  it("dos logos en la misma página no comparten id de gradiente (useId)", () => {
    const { container } = render(
      <>
        <YnaraMark />
        <YnaraMark />
      </>,
    );
    const ids = [...container.querySelectorAll("linearGradient")].map((g) => g.id);
    expect(ids.length).toBeGreaterThan(0);
    expect(new Set(ids).size).toBe(ids.length); // todos únicos
  });
});
