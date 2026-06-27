import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const { useOnboardingStore } = await import("../store");
const { SobreVosStep } = await import("./SobreVosStep");

beforeEach(() => {
  useOnboardingStore.getState().reset();
});

describe("SobreVosStep", () => {
  it("revela '¿Qué estudiás?' solo al elegir una dedicación con estudio", () => {
    render(<SobreVosStep />);
    // Sin dedicación elegida, el campo condicional no está.
    expect(screen.queryByPlaceholderText(/Ingeniería/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Estudio" }));
    expect(screen.getByPlaceholderText(/Ingeniería/i)).toBeInTheDocument();
    // "Estudio" no muestra el campo de trabajo.
    expect(screen.queryByPlaceholderText(/Diseño, ventas/i)).not.toBeInTheDocument();
  });

  it("muestra los campos siempre visibles y el botón para seguir", () => {
    render(<SobreVosStep />);
    expect(screen.getByPlaceholderText(/organizarme/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/música, programación/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /seguir/i })).toBeInTheDocument();
  });

  it("'Ambos' revela estudio y trabajo a la vez", () => {
    render(<SobreVosStep />);
    fireEvent.click(screen.getByRole("button", { name: "Ambos" }));
    expect(screen.getByPlaceholderText(/Ingeniería/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Diseño, ventas/i)).toBeInTheDocument();
  });
});
