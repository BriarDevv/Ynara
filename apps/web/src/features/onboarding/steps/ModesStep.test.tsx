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

// DEFAULT_MODE = "productividad" → label "Productividad" (única pre-marcada).
function defaultModeCard(): HTMLElement {
  return screen.getByRole("button", { name: /Productividad/i });
}

describe("ModesStep", () => {
  it("pre-marca el modo por default cuando el draft no tiene modos", () => {
    render(<ModesStep />);
    expect(defaultModeCard()).toHaveAttribute("aria-pressed", "true");
  });

  it('muestra el error "Elegí al menos uno" al submitear sin ningún modo', async () => {
    const user = userEvent.setup();
    render(<ModesStep />);

    // Deselecciono el único modo pre-marcado (productividad).
    await user.click(defaultModeCard());
    expect(defaultModeCard()).toHaveAttribute("aria-pressed", "false");

    await user.click(screen.getByRole("button", { name: /seguir/i }));

    const error = await screen.findByRole("alert");
    expect(error).toHaveTextContent("Elegí al menos uno");
  });

  it("limpia el error al volver a elegir un modo", async () => {
    const user = userEvent.setup();
    render(<ModesStep />);

    await user.click(defaultModeCard());
    await user.click(screen.getByRole("button", { name: /seguir/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    // Reselecciono un modo: el error se borra (toggle llama setError(null)).
    await user.click(defaultModeCard());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
