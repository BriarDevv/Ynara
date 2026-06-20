import { render, screen } from "@testing-library/react";
import type { MemorySearchHit } from "@ynara/shared-schemas";
import { describe, expect, it, vi } from "vitest";

// next/link → <a> simple para jsdom (no necesitamos el router acá).
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// biome-ignore lint/style/useImportType: React se usa en el mock JSX de arriba
import React from "react";
import { SearchResultRow } from "./SearchResultRow";

const NOW = new Date("2026-06-20T12:00:00.000Z");

function makeHit(snippet: string): MemorySearchHit {
  return {
    layer: "semantic",
    ref: "abc-123",
    snippet,
    score: 0.9,
    occurred_at: null,
  };
}

function renderRow(snippet: string, query?: string) {
  return render(
    <ul>
      <SearchResultRow hit={makeHit(snippet)} now={NOW} index={0} query={query} />
    </ul>,
  );
}

describe("SearchResultRow — resaltado", () => {
  it("envuelve la coincidencia en <mark> conservando el casing original", () => {
    const { container } = renderRow("Estás escribiendo tu Tesis sobre redes", "tesis");
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(1);
    // Case-insensitive: matchea "Tesis" aunque la query sea "tesis".
    expect(marks[0]?.textContent).toBe("Tesis");
  });

  it("resalta todas las ocurrencias del término", () => {
    const { container } = renderRow("foco, más foco y siempre foco", "foco");
    expect(container.querySelectorAll("mark")).toHaveLength(3);
  });

  it("sin query no resalta nada y muestra el snippet completo", () => {
    const { container } = renderRow("Estás escribiendo tu tesis");
    expect(container.querySelectorAll("mark")).toHaveLength(0);
    expect(screen.getByText("Estás escribiendo tu tesis")).toBeInTheDocument();
  });

  it("trata la query como texto literal (no como regex)", () => {
    // Si no se escapara, "t.sis" matchearía "tesis"; escapado, no matchea.
    const { container } = renderRow("Estás escribiendo tu tesis", "t.sis");
    expect(container.querySelectorAll("mark")).toHaveLength(0);
  });
});
