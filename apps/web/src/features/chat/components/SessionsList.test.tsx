import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/features/chat/store";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const { SessionsList } = await import("./SessionsList");

beforeEach(() => {
  push.mockClear();
  useChatStore.getState().reset();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("SessionsList", () => {
  it("no renderiza nada cuando no hay sesiones", () => {
    const { container } = render(<SessionsList />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lista las sesiones por recencia, con preview, y navega al click", () => {
    vi.setSystemTime(1000);
    const a = useChatStore.getState().createSession("estudio");
    useChatStore.getState().appendUserMessage(a, "tema de estudio");
    vi.setSystemTime(2000);
    const b = useChatStore.getState().createSession("vida");
    useChatStore.getState().appendUserMessage(b, "charla casual");

    render(<SessionsList />);
    const texts = screen.getAllByRole("button").map((el) => el.textContent ?? "");
    // b (vida, updatedAt 2000) va primero; a (estudio, 1000) después.
    expect(texts[0]).toContain("charla casual");
    expect(texts[1]).toContain("tema de estudio");

    fireEvent.click(screen.getByRole("button", { name: /charla casual/i }));
    expect(push).toHaveBeenCalledWith(`/chat/${b}`);
  });

  it("muestra 'Conversación vacía' si la sesión no tiene mensajes", () => {
    vi.setSystemTime(1000);
    useChatStore.getState().createSession("memoria");
    render(<SessionsList />);
    expect(screen.getByText("Conversación vacía")).toBeInTheDocument();
  });
});
