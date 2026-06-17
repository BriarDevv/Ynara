import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/features/chat/store";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

// jsdom no implementa showModal/close del <dialog> (igual que Sheet.test).
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false;
  };
});

const { ModeSwitcher } = await import("./ModeSwitcher");

const clickMode = (label: string) => {
  const button = screen.getByText(label, { exact: true }).closest("button");
  expect(button).not.toBeNull();
  fireEvent.click(button as HTMLButtonElement);
};

beforeEach(() => {
  push.mockClear();
  useChatStore.getState().reset();
});

describe("ModeSwitcher", () => {
  it("lista los 5 modos y marca el actual", () => {
    render(<ModeSwitcher open onClose={() => {}} currentMode="estudio" />);
    expect(screen.getByRole("heading", { name: /cambiar de modo/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(5);
    expect(screen.getByText("Actual")).toBeInTheDocument();
  });

  it("elegir otro modo crea una sesión nueva, navega y cierra", () => {
    const onClose = vi.fn();
    render(<ModeSwitcher open onClose={onClose} currentMode="estudio" />);
    clickMode("Vida");

    const sessions = Object.values(useChatStore.getState().sessions);
    expect(sessions).toHaveLength(1);
    expect(sessions[0]?.mode).toBe("vida");
    expect(push).toHaveBeenCalledWith(`/chat/${sessions[0]?.id}`);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("elegir el modo actual solo cierra (sin sesión nueva ni navegación)", () => {
    const onClose = vi.fn();
    render(<ModeSwitcher open onClose={onClose} currentMode="estudio" />);
    clickMode("Estudio");

    expect(Object.values(useChatStore.getState().sessions)).toHaveLength(0);
    expect(push).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("no renderiza la lista cuando está cerrado", () => {
    render(<ModeSwitcher open={false} onClose={() => {}} currentMode="estudio" />);
    expect(screen.queryByText(/cambiar de modo/i)).not.toBeInTheDocument();
  });
});
