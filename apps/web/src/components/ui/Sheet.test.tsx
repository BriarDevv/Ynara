import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { Sheet } from "./Sheet";

// jsdom no implementa showModal/close del <dialog>: los stubeamos para que el
// efecto de sincronización no explote y `open` refleje el estado.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false;
  };
});

describe("Sheet", () => {
  it("renderiza título y contenido cuando está abierto", () => {
    render(
      <Sheet open onClose={() => {}} title="Cambiar modo">
        <p>Contenido del sheet</p>
      </Sheet>,
    );
    expect(screen.getByRole("heading", { name: "Cambiar modo" })).toBeInTheDocument();
    expect(screen.getByText("Contenido del sheet")).toBeInTheDocument();
  });

  it("no renderiza el contenido cuando está cerrado", () => {
    render(
      <Sheet open={false} onClose={() => {}} title="Cambiar modo">
        <p>Contenido del sheet</p>
      </Sheet>,
    );
    expect(screen.queryByText("Contenido del sheet")).not.toBeInTheDocument();
  });

  it("cierra al clickear el backdrop (el propio <dialog>)", () => {
    const onClose = vi.fn();
    const { container } = render(
      <Sheet open onClose={onClose} title="Cambiar modo">
        <p>Contenido del sheet</p>
      </Sheet>,
    );
    const dialog = container.querySelector("dialog");
    expect(dialog).not.toBeNull();
    fireEvent.click(dialog as HTMLDialogElement);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("no cierra al clickear dentro del panel (stopPropagation)", () => {
    const onClose = vi.fn();
    render(
      <Sheet open onClose={onClose} title="Cambiar modo">
        <p>Contenido del sheet</p>
      </Sheet>,
    );
    fireEvent.click(screen.getByText("Contenido del sheet"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("expone aria-labelledby apuntando al título", () => {
    const { container } = render(
      <Sheet open onClose={() => {}} title="Cambiar modo">
        <p>x</p>
      </Sheet>,
    );
    const dialog = container.querySelector("dialog");
    const heading = screen.getByRole("heading", { name: "Cambiar modo" });
    expect(dialog?.getAttribute("aria-labelledby")).toBe(heading.id);
  });
});
