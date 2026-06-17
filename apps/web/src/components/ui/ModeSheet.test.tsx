import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { useActiveModeStore } from "@/stores/mode";
import { ModeSheet } from "./ModeSheet";

// jsdom no implementa showModal/close del <dialog> (igual que Sheet.test).
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
});

const clickMode = (label: string) => {
  const button = screen.getByText(label, { exact: true }).closest("button");
  expect(button).not.toBeNull();
  fireEvent.click(button as HTMLButtonElement);
};

describe("ModeSheet", () => {
  it("lista los 5 modos y marca el actual", () => {
    render(<ModeSheet open onClose={() => {}} current="estudio" />);
    expect(screen.getByRole("heading", { name: /elegí cómo te acompaño/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(5);
    expect(screen.getByText("Estudio", { exact: true }).closest("button")).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  it("elegir un modo fija el modo global, llama onAfterPick y cierra", () => {
    const onClose = vi.fn();
    const onAfterPick = vi.fn();
    render(<ModeSheet open onClose={onClose} current="estudio" onAfterPick={onAfterPick} />);
    clickMode("Vida");

    expect(useActiveModeStore.getState().mode).toBe("vida");
    expect(onAfterPick).toHaveBeenCalledWith("vida");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("no renderiza el contenido cuando está cerrado", () => {
    render(<ModeSheet open={false} onClose={() => {}} current="estudio" />);
    expect(screen.queryByText(/elegí cómo te acompaño/i)).not.toBeInTheDocument();
  });
});
