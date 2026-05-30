import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useA11yStore } from "@/stores/a11y";
import { A11yStep } from "./A11yStep";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

beforeEach(() => {
  useA11yStore.getState().reset();
  document.documentElement.className = "";
});

afterEach(() => {
  useA11yStore.getState().reset();
  document.documentElement.className = "";
});

describe("A11yStep", () => {
  it('aplica la clase text-size-lg al <html> al elegir "Grande"', async () => {
    const user = userEvent.setup();
    render(<A11yStep />);

    await user.click(screen.getByRole("radio", { name: "Grande" }));

    expect(document.documentElement).toHaveClass("text-size-lg");
    expect(document.documentElement).not.toHaveClass("text-size-md");
    expect(useA11yStore.getState().textSize).toBe("lg");
  });

  it("aplica la clase theme-high-contrast al activar el toggle de contraste", async () => {
    const user = userEvent.setup();
    render(<A11yStep />);

    const contrastToggle = screen.getByRole("switch", { name: /contraste alto/i });
    expect(contrastToggle).toHaveAttribute("aria-checked", "false");

    await user.click(contrastToggle);

    expect(document.documentElement).toHaveClass("theme-high-contrast");
    expect(useA11yStore.getState().highContrast).toBe(true);
  });

  it("quita theme-high-contrast al desactivar el toggle de contraste", async () => {
    const user = userEvent.setup();
    render(<A11yStep />);

    const contrastToggle = screen.getByRole("switch", { name: /contraste alto/i });
    await user.click(contrastToggle);
    expect(document.documentElement).toHaveClass("theme-high-contrast");

    await user.click(contrastToggle);
    expect(document.documentElement).not.toHaveClass("theme-high-contrast");
  });

  it('aplica motion-off y motion="reduce" al activar "Reducir animaciones"', async () => {
    const user = userEvent.setup();
    render(<A11yStep />);

    const motionToggle = screen.getByRole("switch", { name: /reducir animaciones/i });
    // matchMedia mockeado devuelve matches=false → arranca destildado.
    expect(motionToggle).toHaveAttribute("aria-checked", "false");

    await user.click(motionToggle);

    expect(document.documentElement).toHaveClass("motion-off");
    expect(useA11yStore.getState().motion).toBe("reduce");
  });
});
