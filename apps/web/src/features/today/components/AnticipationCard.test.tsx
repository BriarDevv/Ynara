import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Anticipation } from "../anticipations";
import { AnticipationCard } from "./AnticipationCard";

const base: Anticipation = {
  id: "ant-test-001",
  kind: "Anticipación",
  time: "10:30",
  text: "Tenés 90 min libres antes de la reunión. ¿Bloqueo un tiempo de foco para la propuesta?",
  mode: "productividad",
  actions: [{ label: "Sí, bloquealo", primary: true }, { label: "Ahora no" }],
};

describe("AnticipationCard", () => {
  it("muestra el texto y la hora de la anticipación", () => {
    render(<AnticipationCard anticipation={base} onDismiss={vi.fn()} />);
    expect(screen.getByText(base.text)).toBeInTheDocument();
    expect(screen.getByText("10:30")).toBeInTheDocument();
  });

  it("muestra el badge del kind y el nombre 'Ynara'", () => {
    render(<AnticipationCard anticipation={base} onDismiss={vi.fn()} />);
    expect(screen.getByText("Ynara")).toBeInTheDocument();
    expect(screen.getByText("Anticipación")).toBeInTheDocument();
  });

  it("renderiza los botones de acción con sus labels", () => {
    render(<AnticipationCard anticipation={base} onDismiss={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Sí, bloquealo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ahora no" })).toBeInTheDocument();
  });

  it("llama onDismiss al clickear el botón primario", () => {
    const onDismiss = vi.fn();
    render(<AnticipationCard anticipation={base} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button", { name: "Sí, bloquealo" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("llama onDismiss al clickear el botón secundario", () => {
    const onDismiss = vi.fn();
    render(<AnticipationCard anticipation={base} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button", { name: "Ahora no" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("es accesible: tiene aria-label descriptivo en el article", () => {
    render(<AnticipationCard anticipation={base} onDismiss={vi.fn()} />);
    expect(screen.getByRole("article")).toHaveAttribute(
      "aria-label",
      `Anticipación de Ynara: ${base.text}`,
    );
  });
});
