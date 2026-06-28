import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useOnboardingStore } from "../store";
import { ModesStep } from "./ModesStep";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

beforeEach(() => {
  useOnboardingStore.getState().reset();
});

afterEach(() => {
  useOnboardingStore.getState().reset();
});

function modeCard(name: RegExp): HTMLElement {
  return screen.getByRole("button", { name });
}

describe("ModesStep", () => {
  it("no pre-marca ningún modo: el primer pick real lidera", () => {
    render(<ModesStep />);
    // Antes 'Productividad' venía pre-pineada y siempre quedaba de líder; ahora
    // arranca sin selección para que el modo activo refleje el primer modo que el
    // usuario elige de verdad.
    expect(modeCard(/Productividad/i)).toHaveAttribute("aria-pressed", "false");
    expect(modeCard(/Estudio/i)).toHaveAttribute("aria-pressed", "false");
  });

  it('muestra el error "Elegí al menos uno" al submitear sin ningún modo', async () => {
    const user = userEvent.setup();
    render(<ModesStep />);

    await user.click(screen.getByRole("button", { name: /seguir/i }));

    const error = await screen.findByRole("alert");
    expect(error).toHaveTextContent("Elegí al menos uno");
  });

  it("limpia el error al elegir un modo", async () => {
    const user = userEvent.setup();
    render(<ModesStep />);

    await user.click(screen.getByRole("button", { name: /seguir/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    // Elegir un modo borra el error (toggle llama setError(null)).
    await user.click(modeCard(/Productividad/i));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("el primer modo elegido lidera interestedModes[0]", async () => {
    const user = userEvent.setup();
    render(<ModesStep />);

    // Elijo Estudio primero, después Vida: Estudio debe quedar de líder (índice 0),
    // que es lo que useActiveMode/useCompleteOnboarding usan para el modo activo.
    // `^Vida` anclado: "Productividad" también contiene "vida" como substring.
    await user.click(modeCard(/Estudio/i));
    await user.click(modeCard(/^Vida/i));
    await user.click(screen.getByRole("button", { name: /seguir/i }));

    expect(useOnboardingStore.getState().interestedModes[0]).toBe("estudio");
  });
});
