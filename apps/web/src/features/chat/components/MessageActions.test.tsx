import { render, screen } from "@testing-library/react";
import type { Action } from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";
import { MessageActions } from "./MessageActions";

function action(
  name: string,
  id = "a1",
  result: Action["result"] = { status: "not_wired" },
): Action {
  return { id, name, arguments: {}, result };
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

  it("muestra el fallo (no un éxito inventado) cuando result trae error", () => {
    render(
      <MessageActions
        actions={[action("calendar.create_event", "a1", { error: { code: "boom", message: "x" } })]}
        mode="productividad"
      />,
    );
    expect(screen.getByText("No se pudo agendar")).toBeInTheDocument();
    expect(screen.queryByText("Agendado")).not.toBeInTheDocument();
  });

  it("muestra el éxito cuando result.status es ok (sin error)", () => {
    render(
      <MessageActions actions={[action("memory.write", "a1", { status: "ok" })]} mode="memoria" />,
    );
    expect(screen.getByText("Guardado en tu memoria")).toBeInTheDocument();
  });

  it("un fallo de acción desconocida cae al label genérico de error", () => {
    render(
      <MessageActions
        actions={[action("tool.x", "a1", { error: { code: "e", message: "m" } })]}
        mode="vida"
      />,
    );
    expect(screen.getByText("No se pudo completar la acción")).toBeInTheDocument();
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
