import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TextField } from "./TextField";

describe("TextField · wiring de accesibilidad", () => {
  it("asocia el label con el input vía htmlFor/id", () => {
    render(<TextField label="Tu nombre" />);
    const input = screen.getByLabelText("Tu nombre");
    expect(input).toBeDefined();
    expect(input.tagName).toBe("INPUT");
  });

  it("expone el hint vía aria-describedby cuando no hay error", () => {
    render(<TextField label="Email" hint="Lo usamos para entrar" />);
    const input = screen.getByLabelText("Email");
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    const hint = screen.getByText("Lo usamos para entrar");
    expect(describedBy).toContain(hint.id);
    // sin error → no es inválido
    expect(input.getAttribute("aria-invalid")).toBeNull();
  });

  it("marca el campo inválido y anuncia el error con role=alert", () => {
    render(<TextField label="Email" error="Email inválido" />);
    const input = screen.getByLabelText("Email");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toBe("Email inválido");
    expect(input.getAttribute("aria-describedby")).toContain(alert.id);
  });

  it("sin label/hint/error no agrega aria-describedby espurio", () => {
    render(<TextField placeholder="Escribí…" />);
    const input = screen.getByPlaceholderText("Escribí…");
    expect(input.getAttribute("aria-describedby")).toBeNull();
  });
});
