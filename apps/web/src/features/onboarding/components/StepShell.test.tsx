import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StepShell } from "./StepShell";

describe("StepShell", () => {
  it("standard: el título usa text-title", () => {
    render(
      <StepShell title="Tu nombre">
        <p>contenido</p>
      </StepShell>,
    );
    const heading = screen.getByRole("heading", { level: 1, name: "Tu nombre" });
    expect(heading.className).toContain("text-title");
  });

  it("editorial: el título usa text-display", () => {
    render(
      <StepShell variant="editorial" title="Antes que nada">
        <p>contenido</p>
      </StepShell>,
    );
    const heading = screen.getByRole("heading", { level: 1, name: "Antes que nada" });
    expect(heading.className).toContain("text-display");
  });

  it("renderiza subtitle, footer y el slot background", () => {
    render(
      <StepShell
        title="X"
        subtitle="Un subtítulo"
        footer={<button type="button">Seguir</button>}
        background={<svg data-testid="bg" />}
      >
        <p>contenido</p>
      </StepShell>,
    );
    expect(screen.getByText("Un subtítulo")).toBeDefined();
    expect(screen.getByRole("button", { name: "Seguir" })).toBeDefined();
    // el background es decorativo: va dentro de un contenedor aria-hidden
    const bg = screen.getByTestId("bg");
    expect(bg.closest("[aria-hidden='true']")).not.toBeNull();
  });
});
