import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyStateCard } from "./EmptyStateCard";

describe("EmptyStateCard", () => {
  it("renderiza title y hint", () => {
    render(<EmptyStateCard title="Todavía no hay nada" hint="Empezá una conversación" />);
    expect(screen.getByText("Todavía no hay nada")).toBeDefined();
    expect(screen.getByText("Empezá una conversación")).toBeDefined();
  });

  it("no dibuja ningún fondo gráfico (lenguaje sobrio)", () => {
    const { container } = render(<EmptyStateCard title="Vacío" />);
    expect(container.querySelector("svg")).toBeNull();
  });
});
