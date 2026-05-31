import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptChip } from "./PromptChip";

describe("PromptChip", () => {
  it("renderiza el label y dispara onClick", () => {
    const onClick = vi.fn();
    render(<PromptChip label="¿Qué hago hoy?" onClick={onClick} />);
    const chip = screen.getByRole("button", { name: "¿Qué hago hoy?" });
    fireEvent.click(chip);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("deshabilitado no dispara onClick", () => {
    const onClick = vi.fn();
    render(<PromptChip label="Resumime el día" onClick={onClick} disabled />);
    const chip = screen.getByRole("button", { name: "Resumime el día" });
    expect(chip).toHaveProperty("disabled", true);
    fireEvent.click(chip);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("el ícono leading es decorativo (aria-hidden)", () => {
    render(
      <PromptChip label="Conectá ideas" onClick={() => {}} leading={<svg data-testid="icono" />} />,
    );
    const icon = screen.getByTestId("icono");
    expect(icon.parentElement?.getAttribute("aria-hidden")).toBe("true");
  });
});
