import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useA11yStore } from "@/stores/a11y";
import { A11yStep } from "./A11yStep";

// useOnboardingNav usa next/navigation useRouter; mockeamos el router para
// que el componente no dependa del App Router real (mismo patrón que el
// resto de tests de steps).
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

// El hook que cierra el flujo hace fetch al backend + escribe al user
// store + dispara navegación. Lo mockeamos para que el test no salga del
// componente.
const completeMock = vi.fn();
let mockState: {
  isPending: boolean;
  isCelebrating: boolean;
  error: string | null;
} = { isPending: false, isCelebrating: false, error: null };

vi.mock("../hooks/useCompleteOnboarding", () => ({
  useCompleteOnboarding: () => ({
    complete: completeMock,
    triggerOutroComplete: vi.fn(),
    isPending: mockState.isPending,
    isCelebrating: mockState.isCelebrating,
    error: mockState.error,
  }),
}));

beforeEach(() => {
  useA11yStore.getState().reset();
  completeMock.mockClear();
  mockState = { isPending: false, isCelebrating: false, error: null };
});

afterEach(() => {
  useA11yStore.getState().reset();
});

describe("A11yStep", () => {
  it("monta el shell con título y los 3 controles de a11y", () => {
    render(<A11yStep />);

    // El título del step (STEP_COPY.a11y.title).
    expect(screen.getByRole("heading", { level: 1, name: /cómo se lee/i })).toBeDefined();

    // Los 3 controles: ChipGroup tamaño + 2 Toggles.
    expect(screen.getByText(/TAMAÑO DEL TEXTO/i)).toBeDefined();
    expect(screen.getByText(/Alto contraste/i)).toBeDefined();
    expect(screen.getByText(/Reducir animaciones/i)).toBeDefined();

    // CTA final del onboarding.
    expect(screen.getByRole("button", { name: /^Listo$/i })).toBeDefined();
  });

  it("escribe el tamaño de texto elegido directo en useA11yStore", async () => {
    const user = userEvent.setup();
    render(<A11yStep />);

    // Default del store: textSize = "md".
    expect(useA11yStore.getState().textSize).toBe("md");

    // ChipGroup expone sus opciones como role=radio dentro de role=radiogroup
    // (no como role=button), porque es un control de selección única.
    await user.click(screen.getByRole("radio", { name: "Chico" }));
    expect(useA11yStore.getState().textSize).toBe("sm");

    await user.click(screen.getByRole("radio", { name: "Grande" }));
    expect(useA11yStore.getState().textSize).toBe("lg");
  });

  it("activa alto contraste cuando se prende su toggle", async () => {
    const user = userEvent.setup();
    render(<A11yStep />);

    expect(useA11yStore.getState().highContrast).toBe(false);

    await user.click(screen.getByRole("switch", { name: /Alto contraste/i }));
    expect(useA11yStore.getState().highContrast).toBe(true);
  });

  it("mapea el toggle de reducir animaciones a motion=reduce", async () => {
    const user = userEvent.setup();
    render(<A11yStep />);

    // Default: motion = "auto".
    expect(useA11yStore.getState().motion).toBe("auto");

    await user.click(screen.getByRole("switch", { name: /Reducir animaciones/i }));
    expect(useA11yStore.getState().motion).toBe("reduce");

    // Volver a apagarlo lo lleva a "auto", no a "normal" (la opción de
    // forzar animaciones queda para Ajustes post-MVP — A11yStep es binario).
    await user.click(screen.getByRole("switch", { name: /Reducir animaciones/i }));
    expect(useA11yStore.getState().motion).toBe("auto");
  });

  it("llama a complete() al clickear el botón Listo", async () => {
    const user = userEvent.setup();
    render(<A11yStep />);

    await user.click(screen.getByRole("button", { name: /^Listo$/i }));
    expect(completeMock).toHaveBeenCalledTimes(1);
  });

  it("muestra Guardando… y deshabilita el botón mientras isPending", () => {
    mockState = { isPending: true, isCelebrating: false, error: null };
    render(<A11yStep />);

    const cta = screen.getByRole("button", { name: /Guardando/i });
    expect(cta).toBeDisabled();
  });

  it("renderiza el error inline con role=alert cuando complete falla", () => {
    mockState = {
      isPending: false,
      isCelebrating: false,
      error: "No pudimos guardar tus datos. Reintentá.",
    };
    render(<A11yStep />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("No pudimos guardar");
  });

  it("monta el CelebrationOutro en lugar del shell cuando isCelebrating", () => {
    mockState = { isPending: false, isCelebrating: true, error: null };
    render(<A11yStep />);

    // El shell del step no debe estar montado (sin h1 del título del step).
    expect(screen.queryByRole("heading", { level: 1, name: /cómo se lee/i })).toBeNull();
  });
});
