import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AppTemplate from "./template";

describe("AppTemplate", () => {
  it("envuelve a los hijos con la transición de pantalla (anim-screen-in)", () => {
    const { container, getByText } = render(
      <AppTemplate>
        <p>contenido</p>
      </AppTemplate>,
    );
    expect(getByText("contenido")).toBeInTheDocument();
    const wrapper = container.firstElementChild;
    // La entrada de pantalla (§8.3) la neutraliza la cascada global de
    // reduced-motion; acá basta con verificar que el wrapper la lleva.
    // Opacidad pura (sin transform) para no anclar overlays fixed al template.
    expect(wrapper).toHaveClass("anim-screen-in");
    // Layout que conserva el contrato de scroll del shell (h-full / min-h-full).
    expect(wrapper).toHaveClass("flex", "flex-1", "flex-col");
  });
});
