import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useThemeStore } from "@/stores/theme";

// Mock del helper con una función plana (inmune a clearMocks/restoreMocks) que
// registra la llamada y corre el update — así verificamos que el toggle pasa
// por la View Transition y que el cambio efectivamente ocurre.
let svtCalls = 0;
vi.mock("@/lib/viewTransition", () => ({
  startViewTransition: (update: () => void) => {
    svtCalls += 1;
    update();
  },
}));

import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    svtCalls = 0;
  });

  afterEach(() => {
    useThemeStore.getState().reset();
    localStorage.clear();
  });

  it("alterna el tema dentro de una View Transition (startViewTransition)", () => {
    useThemeStore.setState({ theme: "light" });
    render(<ThemeToggle />);

    const btn = screen.getByRole("button", { name: "Cambiar tema" });
    expect(btn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(btn);

    expect(svtCalls).toBe(1);
    expect(useThemeStore.getState().theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Cambiar tema" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
