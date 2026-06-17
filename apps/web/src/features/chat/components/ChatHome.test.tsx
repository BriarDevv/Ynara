import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/features/chat/store";
import { useActiveModeStore } from "@/stores/mode";
import { useUserStore } from "@/stores/user";

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

const { ChatHome } = await import("./ChatHome");

beforeEach(() => {
  push.mockClear();
  useChatStore.getState().reset();
  useActiveModeStore.getState().reset();
  useUserStore.getState().setInterestedModes([]);
});

describe("ChatHome", () => {
  it("muestra el título y la acción de nueva conversación (sin muro de modos)", () => {
    render(<ChatHome />);
    expect(screen.getByRole("heading", { name: /de qué hablamos/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /nueva conversación/i })).toBeInTheDocument();
  });

  it("arranca la conversación en el modo activo (default) y navega", () => {
    render(<ChatHome />);
    fireEvent.click(screen.getByRole("button", { name: /nueva conversación/i }));

    const sessions = Object.values(useChatStore.getState().sessions);
    expect(sessions).toHaveLength(1);
    // Sin override ni modos de interés, el activo es el default de marca.
    expect(sessions[0]?.mode).toBe("productividad");
    expect(push).toHaveBeenCalledWith(`/chat/${sessions[0]?.id}`);
  });

  it("usa el modo activo elegido en el picker global", () => {
    useActiveModeStore.getState().setMode("estudio");
    render(<ChatHome />);
    fireEvent.click(screen.getByRole("button", { name: /nueva conversación/i }));

    const sessions = Object.values(useChatStore.getState().sessions);
    expect(sessions[0]?.mode).toBe("estudio");
  });

  it("el chip abre el picker de modos (arranca cerrado)", () => {
    render(<ChatHome />);
    expect(
      screen.queryByRole("heading", { name: /elegí cómo te acompaño/i }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /cambiar de modo/i }));
    expect(screen.getByRole("heading", { name: /elegí cómo te acompaño/i })).toBeInTheDocument();
  });
});
