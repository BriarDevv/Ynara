import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useOnboardingStore } from "../store";
import { MoodStep } from "./MoodStep";

// useOnboardingNav usa next/navigation useRouter; mockeamos el router para
// que el componente no dependa del App Router real.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

beforeEach(() => {
  useOnboardingStore.getState().reset();
});

afterEach(() => {
  useOnboardingStore.getState().reset();
});

function moodCard(label: string): HTMLElement {
  return screen.getByRole("button", { name: new RegExp(label, "i") });
}

describe("MoodStep", () => {
  it("deshabilita las opciones no seleccionadas al alcanzar el máximo de 2 moods", async () => {
    const user = userEvent.setup();
    render(<MoodStep />);

    const tranquilo = moodCard("Tranquilo, con tiempo");
    const ocupado = moodCard("Ocupado, varias cosas");
    const estresado = moodCard("Estresado");
    const confuso = moodCard("Confuso, no sé por dónde arrancar");

    // Antes de elegir nada, ninguna está deshabilitada.
    expect(estresado).toBeEnabled();
    expect(confuso).toBeEnabled();

    await user.click(tranquilo);
    await user.click(ocupado);

    // Al llegar a 2 seleccionadas, las no seleccionadas quedan deshabilitadas.
    expect(tranquilo).toBeEnabled();
    expect(ocupado).toBeEnabled();
    expect(estresado).toBeDisabled();
    expect(confuso).toBeDisabled();
  });

  it("permite re-habilitar una opción al deseleccionar uno de los moods elegidos", async () => {
    const user = userEvent.setup();
    render(<MoodStep />);

    const tranquilo = moodCard("Tranquilo, con tiempo");
    const ocupado = moodCard("Ocupado, varias cosas");
    const estresado = moodCard("Estresado");

    await user.click(tranquilo);
    await user.click(ocupado);
    expect(estresado).toBeDisabled();

    // Deselecciono una: vuelve a haber cupo, las demás se re-habilitan.
    await user.click(ocupado);
    expect(estresado).toBeEnabled();
  });
});
