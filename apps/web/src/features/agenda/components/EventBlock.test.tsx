import { render, screen } from "@testing-library/react";
import type { AgendaEvent } from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";
import { EventBlock } from "./EventBlock";

const at = (h: number, m: number) => new Date(2026, 4, 7, h, m).toISOString();

const base: AgendaEvent = {
  id: "0193d001-0000-4000-8000-000000000001",
  title: "Clase de Sistemas",
  start_at: at(10, 0),
  duration_min: 90,
  mode: "estudio",
  status: "confirmed",
  location: "Aula Magna",
};

function renderBlock(event: AgendaEvent) {
  render(
    <ul>
      <EventBlock event={event} index={0} />
    </ul>,
  );
}

describe("EventBlock", () => {
  it("muestra título, rango horario derivado y lugar", () => {
    renderBlock(base);
    expect(screen.getByText("Clase de Sistemas")).toBeInTheDocument();
    expect(screen.getByText("10:00 – 11:30")).toBeInTheDocument();
    expect(screen.getByText("Aula Magna")).toBeInTheDocument();
  });

  it("un evento confirmado no muestra tag de estado", () => {
    renderBlock(base);
    expect(screen.queryByText("Tentativo")).not.toBeInTheDocument();
    expect(screen.queryByText("Cancelado")).not.toBeInTheDocument();
  });

  it("un evento tentativo muestra su tag", () => {
    renderBlock({ ...base, status: "tentative", location: null });
    expect(screen.getByText("Tentativo")).toBeInTheDocument();
  });

  it("un evento cancelado tacha el título y muestra su tag", () => {
    renderBlock({ ...base, status: "cancelled" });
    expect(screen.getByText("Cancelado")).toBeInTheDocument();
    expect(screen.getByText("Clase de Sistemas")).toHaveClass("line-through");
  });

  it("sin lugar no renderiza el subtítulo", () => {
    renderBlock({ ...base, location: null });
    expect(screen.queryByText("Aula Magna")).not.toBeInTheDocument();
  });
});
