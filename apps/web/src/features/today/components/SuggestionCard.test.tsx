import { render, screen } from "@testing-library/react";
import type { Suggestion } from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";
import { SuggestionCard } from "./SuggestionCard";

const base: Suggestion = {
  id: "0193c002-0000-4000-8000-000000000001",
  title: "Bloque de foco 10:30–12:00",
  why: "90 min sin notificaciones para la propuesta Õmi",
  mode: "productividad",
};

function renderCard(suggestion: Suggestion) {
  render(
    <ul>
      <SuggestionCard suggestion={suggestion} index={0} />
    </ul>,
  );
}

describe("SuggestionCard", () => {
  it("muestra el título y el porqué", () => {
    renderCard(base);
    expect(screen.getByText("Bloque de foco 10:30–12:00")).toBeInTheDocument();
    expect(screen.getByText("90 min sin notificaciones para la propuesta Õmi")).toBeInTheDocument();
  });

  it("renderiza una sugerencia transversal (mode null) sin romper", () => {
    renderCard({ ...base, mode: null, title: "Pausá 10 min", why: "Llevás 90 min en pantalla" });
    expect(screen.getByText("Pausá 10 min")).toBeInTheDocument();
    expect(screen.getByText("Llevás 90 min en pantalla")).toBeInTheDocument();
  });
});
