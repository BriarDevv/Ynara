import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { useActiveModeStore } from "@/stores/mode";
import { useUserStore } from "@/stores/user";

// jsdom no implementa showModal/close del <dialog>.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false;
  };
});

beforeEach(() => {
  useActiveModeStore.getState().reset();
  useUserStore.getState().setInterestedModes([]);
});

const { CheckinSheet } = await import("./CheckinSheet");

describe("CheckinSheet", () => {
  it("renderiza el título del check-in cuando está abierto", () => {
    render(<CheckinSheet open onClose={vi.fn()} />);
    expect(screen.getByText("¿Cómo arrancás el día?")).toBeInTheDocument();
  });

  it("no renderiza contenido cuando está cerrado", () => {
    render(<CheckinSheet open={false} onClose={vi.fn()} />);
    expect(screen.queryByText("¿Cómo arrancás el día?")).not.toBeInTheDocument();
  });

  it("muestra los 5 botones de mood", () => {
    render(<CheckinSheet open onClose={vi.fn()} />);
    const moodButtons = screen.getAllByRole("button", {
      name: /tranquilo|ocupado|estresado|cansado|con energía/i,
    });
    expect(moodButtons).toHaveLength(5);
  });

  it("selecciona un mood al clickear", () => {
    render(<CheckinSheet open onClose={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /tranquilo/i });
    expect(btn).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  it("muestra el slider de energía con valor inicial 6", () => {
    render(<CheckinSheet open onClose={vi.fn()} />);
    const slider = screen.getByRole("slider", { name: /energía/i });
    expect(slider).toHaveAttribute("aria-valuenow", "6");
  });

  it("actualiza el slider de energía", () => {
    render(<CheckinSheet open onClose={vi.fn()} />);
    const slider = screen.getByRole("slider", { name: /energía/i });
    fireEvent.change(slider, { target: { value: "8" } });
    expect(slider).toHaveValue("8");
  });

  it("muestra el textarea de nota", () => {
    render(<CheckinSheet open onClose={vi.fn()} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("llama onClose al clickear Listo", () => {
    const onClose = vi.fn();
    render(<CheckinSheet open onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: /listo/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("resetea mood, energía y nota al cerrar y reabrir", () => {
    const { rerender } = render(<CheckinSheet open onClose={vi.fn()} />);
    // Tocar el formulario: elegir mood, subir energía, escribir nota.
    fireEvent.click(screen.getByRole("button", { name: /tranquilo/i }));
    fireEvent.change(screen.getByRole("slider", { name: /energía/i }), { target: { value: "9" } });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "algo en la cabeza" } });
    expect(screen.getByRole("button", { name: /tranquilo/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    // Cerrar (desmonta los hijos) y reabrir: el estado vuelve a los defaults.
    rerender(<CheckinSheet open={false} onClose={vi.fn()} />);
    rerender(<CheckinSheet open onClose={vi.fn()} />);

    expect(screen.getByRole("button", { name: /tranquilo/i })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByRole("slider", { name: /energía/i })).toHaveValue("6");
    expect(screen.getByRole("textbox")).toHaveValue("");
  });
});
