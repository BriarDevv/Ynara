import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/features/chat/store";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false;
  };
});

const { ChatHeader } = await import("./ChatHeader");

beforeEach(() => {
  push.mockClear();
  useChatStore.getState().reset();
});

describe("ChatHeader", () => {
  it("vuelve a /hoy con el botón de atrás", () => {
    render(<ChatHeader mode="estudio" />);
    fireEvent.click(screen.getByRole("button", { name: /volver al inicio/i }));
    expect(push).toHaveBeenCalledWith("/hoy");
  });

  it("abre el ModeSwitcher al tocar el modo (arranca cerrado)", () => {
    render(<ChatHeader mode="estudio" />);
    expect(screen.queryByRole("heading", { name: /cambiar de modo/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /cambiar de modo/i }));
    expect(screen.getByRole("heading", { name: /cambiar de modo/i })).toBeInTheDocument();
  });
});
