import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { YnaraOrb } from "./YnaraOrb";

describe("YnaraOrb", () => {
  it("es decorativo puro: aria-hidden, sin rol ni foco", () => {
    const { container } = render(<YnaraOrb />);
    const orb = container.firstElementChild as HTMLElement;
    expect(orb).toHaveAttribute("aria-hidden");
    expect(orb.querySelector("button, a, [tabindex]")).toBeNull();
  });

  it("respeta el tamaño pedido y el latido calmo por default", () => {
    const { container } = render(<YnaraOrb size={60} />);
    const orb = container.firstElementChild as HTMLElement;
    expect(orb.style.width).toBe("60px");
    expect(orb.style.height).toBe("60px");
    expect(orb.style.getPropertyValue("--orb-beat")).toBe("4200ms");
  });

  it("thinking acelera el latido vía --orb-beat (sin pisar la cascada de motion)", () => {
    const { container } = render(<YnaraOrb thinking />);
    const orb = container.firstElementChild as HTMLElement;
    expect(orb.style.getPropertyValue("--orb-beat")).toBe("1500ms");
  });

  it("se tiñe con el tint del modo activo; sin modo cae al azul de marca", () => {
    const { container: conModo } = render(<YnaraOrb modeId="bienestar" />);
    expect(conModo.innerHTML).toContain("var(--mode-bienestar)");

    const { container: sinModo } = render(<YnaraOrb />);
    expect(sinModo.innerHTML).toContain("var(--color-azul)");
  });

  it("el diamante central conserva la rotación de marca como fallback estático", () => {
    // Bajo reduced-motion la animación (que rota en sus keyframes) se
    // neutraliza: la clase rotate-45 es lo que mantiene el rombo.
    const { container } = render(<YnaraOrb />);
    expect(container.querySelector(".anim-orb-core")?.className).toContain("rotate-45");
  });
});
