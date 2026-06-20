import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { Recap } from "../api";
import { RecapSheet } from "./RecapSheet";

// jsdom no implementa showModal/close del <dialog> (igual que Sheet.test).
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false;
  };
});

const baseRecap: Recap = {
  pending: false,
  date: "2026-06-17T12:00:00-03:00",
  headline: "Un día redondo",
  highlights: ["Cerraste la tesis", "Dormiste mejor"],
};

describe("RecapSheet", () => {
  it("muestra los highlights cuando los hay", () => {
    render(<RecapSheet open onClose={() => {}} recap={baseRecap} />);
    expect(screen.getByText("Cerraste la tesis")).toBeInTheDocument();
    expect(screen.getByText("Dormiste mejor")).toBeInTheDocument();
  });

  it("muestra el headline editorial como título cuando existe", () => {
    render(<RecapSheet open onClose={() => {}} recap={baseRecap} />);
    expect(screen.getByRole("heading", { level: 2, name: "Un día redondo" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /cómo te fue hoy/i })).not.toBeInTheDocument();
  });

  it("cae al título genérico cuando el headline es null o vacío", () => {
    const { rerender } = render(
      <RecapSheet open onClose={() => {}} recap={{ ...baseRecap, headline: null }} />,
    );
    expect(screen.getByRole("heading", { level: 2, name: /cómo te fue hoy/i })).toBeInTheDocument();
    rerender(<RecapSheet open onClose={() => {}} recap={{ ...baseRecap, headline: "" }} />);
    expect(screen.getByRole("heading", { level: 2, name: /cómo te fue hoy/i })).toBeInTheDocument();
  });

  it("muestra el empty-state cuando no hay highlights", () => {
    render(
      <RecapSheet
        open
        onClose={() => {}}
        recap={{ pending: true, date: "2026-06-17T12:00:00-03:00", headline: null, highlights: [] }}
      />,
    );
    expect(screen.getByText(/todavía no hay nada para repasar/i)).toBeInTheDocument();
  });

  it("el CTA dispara onClose", () => {
    const onClose = vi.fn();
    render(<RecapSheet open onClose={onClose} recap={baseRecap} />);
    fireEvent.click(screen.getByRole("button", { name: /cerrar el día/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("no renderiza el contenido cuando está cerrado", () => {
    render(<RecapSheet open={false} onClose={() => {}} recap={baseRecap} />);
    expect(screen.queryByText("Cerraste la tesis")).not.toBeInTheDocument();
  });
});
