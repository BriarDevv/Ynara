import { render, screen } from "@testing-library/react";
import type { Action } from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";
import { MessageActions } from "./MessageActions";

function action(name: string, id = "a1"): Action {
  return { id, name, arguments: {}, result: { status: "not_wired" } };
}

describe("MessageActions", () => {
  it("muestra 'Agendado' para calendar.create_event", () => {
    render(<MessageActions actions={[action("calendar.create_event")]} mode="productividad" />);
    expect(screen.getByText("Agendado")).toBeInTheDocument();
  });

  it("muestra 'Guardado en tu memoria' para memory.write", () => {
    render(<MessageActions actions={[action("memory.write")]} mode="memoria" />);
    expect(screen.getByText("Guardado en tu memoria")).toBeInTheDocument();
  });

  it("cae a un label genérico para una acción desconocida", () => {
    render(<MessageActions actions={[action("tool.desconocida")]} mode="vida" />);
    expect(screen.getByText("Acción ejecutada")).toBeInTheDocument();
  });

  it("no renderiza nada si no hay acciones", () => {
    const { container } = render(<MessageActions actions={[]} mode="vida" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("expone la lista con un nombre accesible", () => {
    render(<MessageActions actions={[action("memory.write")]} mode="memoria" />);
    expect(screen.getByRole("list", { name: /acciones que hizo ynara/i })).toBeInTheDocument();
  });
});
