import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore } from "@/features/chat/store";
import { useUserStore } from "@/stores/user";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const { ChatHome } = await import("./ChatHome");

beforeEach(() => {
  push.mockClear();
  useChatStore.getState().reset();
  useUserStore.getState().setInterestedModes([]);
});

describe("ChatHome", () => {
  it("muestra el título y las 5 opciones de modo", () => {
    render(<ChatHome />);
    expect(screen.getByRole("heading", { name: /de qué hablamos/i })).toBeInTheDocument();
    // Sin sesiones, los únicos botones son las 5 opciones de modo.
    const names = screen.getAllByRole("button").map((b) => b.textContent ?? "");
    expect(names).toHaveLength(5);
    for (const label of ["Productividad", "Estudio", "Bienestar", "Vida", "Memoria"]) {
      expect(names.some((n) => n.includes(label))).toBe(true);
    }
  });

  it("crea una sesión en el modo elegido y navega a la conversación", () => {
    render(<ChatHome />);
    fireEvent.click(screen.getByRole("button", { name: /estudio/i }));

    const sessions = Object.values(useChatStore.getState().sessions);
    expect(sessions).toHaveLength(1);
    expect(sessions[0]?.mode).toBe("estudio");
    expect(push).toHaveBeenCalledWith(`/chat/${sessions[0]?.id}`);
  });

  it("prioriza los modos elegidos en el onboarding (aparecen primero)", () => {
    useUserStore.getState().setInterestedModes(["memoria"]);
    render(<ChatHome />);
    // Sin sesiones, los únicos botones son los 5 modos: el de interés va al tope.
    expect(screen.getAllByRole("button")[0]).toHaveTextContent(/memoria/i);
  });
});
