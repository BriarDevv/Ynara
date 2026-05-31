import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyStateCard } from "./EmptyStateCard";

describe("EmptyStateCard", () => {
  it("renderiza title y hint", () => {
    render(<EmptyStateCard title="Todavía no hay nada" hint="Empezá una conversación" />);
    expect(screen.getByText("Todavía no hay nada")).toBeDefined();
    expect(screen.getByText("Empezá una conversación")).toBeDefined();
  });

  it("sin field no dibuja la Red de memoria", () => {
    const { container } = render(<EmptyStateCard title="Vacío" />);
    expect(container.querySelector("svg")).toBeNull();
  });

  it("con field=true dibuja el MemoryField de @ynara/ui (svg decorativo)", () => {
    const { container } = render(<EmptyStateCard title="Vacío" field />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    // el field es ambiente: no debe anunciarse al lector de pantalla
    expect(svg?.closest("[aria-hidden='true']")).not.toBeNull();
  });
});
