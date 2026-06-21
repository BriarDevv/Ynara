import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/features/chat/store";
import { useActiveModeStore } from "@/stores/mode";

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
  useActiveModeStore.getState().reset();
});

describe("ChatHeader", () => {
  it("vuelve a /hoy con el botón de atrás", () => {
    render(<ChatHeader mode="estudio" />);
    fireEvent.click(screen.getByRole("button", { name: /volver al inicio/i }));
    expect(push).toHaveBeenCalledWith("/hoy");
  });

  it("abre el picker de modo al tocar el chip (arranca cerrado)", () => {
    render(<ChatHeader mode="estudio" />);
    expect(
      screen.queryByRole("heading", { name: /elegí cómo te acompaño/i }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /cambiar de modo/i }));
    expect(screen.getByRole("heading", { name: /elegí cómo te acompaño/i })).toBeInTheDocument();
  });

  it("el orbe late más rápido (thinking) mientras Ynara responde", () => {
    const { container, rerender } = render(<ChatHeader mode="estudio" thinking={false} />);
    const orbBeat = () =>
      container
        .querySelector<HTMLElement>('[style*="--orb-beat"]')
        ?.style.getPropertyValue("--orb-beat");
    expect(orbBeat()).toBe("4200ms");
    rerender(<ChatHeader mode="estudio" thinking />);
    expect(orbBeat()).toBe("1500ms");
  });

  it("elegir otro modo arranca una conversación nueva en ese modo y navega", () => {
    render(<ChatHeader mode="estudio" />);
    fireEvent.click(screen.getByRole("button", { name: /cambiar de modo/i }));
    fireEvent.click(
      screen.getByText("Vida", { exact: true }).closest("button") as HTMLButtonElement,
    );

    const sessions = Object.values(useChatStore.getState().sessions);
    expect(sessions).toHaveLength(1);
    expect(sessions[0]?.mode).toBe("vida");
    expect(useActiveModeStore.getState().mode).toBe("vida");
    expect(push).toHaveBeenCalledWith(`/chat/${sessions[0]?.id}`);
  });
});
