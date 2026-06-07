import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { YnaraWordmark } from "./YnaraWordmark";

describe("YnaraWordmark", () => {
  it("es accesible: un solo role=img con aria-label Ynara", () => {
    const { getAllByRole } = render(<YnaraWordmark />);
    const imgs = getAllByRole("img");
    expect(imgs).toHaveLength(1);
    expect(imgs[0]).toHaveAttribute("aria-label", "Ynara");
  });

  it("renderiza el símbolo + el texto Ynara compartiendo baseline", () => {
    const { container } = render(<YnaraWordmark />);
    const text = container.querySelector("text");
    expect(text?.textContent).toBe("Ynara");
    // Baseline del texto y pies del símbolo en la misma y (19.8).
    expect(text).toHaveAttribute("y", "19.8");
    // El símbolo va dentro de un <g> transformado (no align a mano).
    expect(container.querySelector("g[transform]")).toBeInTheDocument();
  });

  it("el alto fija el ancho por el viewBox (sin deformar)", () => {
    const { container } = render(<YnaraWordmark height={44} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("height", "44");
    // width = 44 * (65.5 / 22) = 131
    expect(svg).toHaveAttribute("width", "131");
  });

  it("la variante mono-light tiñe texto y símbolo en marfil (para Noche)", () => {
    const { container } = render(<YnaraWordmark variant="mono-light" />);
    const html = container.innerHTML;
    expect(html).toContain("var(--color-marfil");
    // mono = silueta plana, sin gradientes.
    expect(html).not.toContain("linearGradient");
  });

  it("la variante color usa los stops oficiales y texto en Noche fijo (fondo claro)", () => {
    const { container } = render(<YnaraWordmark variant="color" />);
    const html = container.innerHTML;
    expect(html).toContain("var(--color-azul");
    // Tono fijo, no `--color-ink-*` que seguiría el tema (se elige por fondo).
    expect(container.querySelector("text")).toHaveAttribute("fill", "var(--color-noche, #242c3f)");
  });
});
