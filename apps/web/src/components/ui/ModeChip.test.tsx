import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ModeChip } from "./ModeChip";

describe("ModeChip", () => {
  it("muestra el label canónico del modo", () => {
    render(<ModeChip modeId="productividad" />);
    expect(screen.getByText("Productividad")).toBeInTheDocument();
  });

  it("permite override del label", () => {
    render(<ModeChip modeId="estudio" label="Modo: Estudio" />);
    expect(screen.getByText("Modo: Estudio")).toBeInTheDocument();
  });

  it("pinta el dot con el tint plano del modo (§3.5)", () => {
    const { container } = render(<ModeChip modeId="memoria" />);
    const dot = container.querySelector<HTMLElement>("[aria-hidden]");
    expect(dot).not.toBeNull();
    expect(dot?.style.backgroundColor).toBe("var(--mode-memoria)");
  });
});
