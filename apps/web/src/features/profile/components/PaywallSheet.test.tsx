import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { PaywallSheet } from "./PaywallSheet";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});

describe("PaywallSheet — smoke", () => {
  it("no renderiza contenido cuando está cerrado", () => {
    render(<PaywallSheet open={false} onClose={vi.fn()} />);
    expect(screen.queryByText(/Activar Premium/i)).not.toBeInTheDocument();
  });

  it("muestra el headline cuando está abierto", () => {
    render(<PaywallSheet open onClose={vi.fn()} />);
    expect(screen.getByText(/no se olvide/i)).toBeInTheDocument();
  });

  it("muestra los 4 beneficios", () => {
    render(<PaywallSheet open onClose={vi.fn()} />);
    expect(screen.getByText("Memoria sin límite")).toBeInTheDocument();
    expect(screen.getByText("Avisos proactivos")).toBeInTheDocument();
    expect(screen.getByText("Modos avanzados")).toBeInTheDocument();
    expect(screen.getByText("Soporte prioritario")).toBeInTheDocument();
  });

  it("muestra el precio", () => {
    render(<PaywallSheet open onClose={vi.fn()} />);
    expect(screen.getByText(/\$6\.900\/mes/i)).toBeInTheDocument();
  });

  it("muestra CTA primario y secundario", () => {
    render(<PaywallSheet open onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: /activar premium/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /quizás después/i })).toBeInTheDocument();
  });

  it("llama onClose al pulsar 'Quizás después'", async () => {
    const onClose = vi.fn();
    render(<PaywallSheet open onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: /quizás después/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("cierra y muestra toast demo al pulsar 'Activar Premium'", async () => {
    const onClose = vi.fn();
    render(<PaywallSheet open onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: /activar premium/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/premium es demo/i)).toBeInTheDocument();
  });
});
