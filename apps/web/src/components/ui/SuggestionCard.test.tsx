import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SuggestionCard } from "./SuggestionCard";

function accentOf(container: HTMLElement): HTMLElement | null {
  return container.querySelector<HTMLElement>("[aria-hidden]");
}

describe("SuggestionCard", () => {
  describe("variante display (sin onClick)", () => {
    function renderDisplay(props: Parameters<typeof SuggestionCard>[0]) {
      return render(
        <ul>
          <SuggestionCard {...props} />
        </ul>,
      );
    }

    it("muestra el título y el subtítulo", () => {
      renderDisplay({
        modeId: "productividad",
        title: "Bloque de foco 10:30–12:00",
        subtitle: "90 min sin notificaciones para la propuesta Õmi",
        staggerIndex: 0,
      });
      expect(screen.getByText("Bloque de foco 10:30–12:00")).toBeInTheDocument();
      expect(
        screen.getByText("90 min sin notificaciones para la propuesta Õmi"),
      ).toBeInTheDocument();
    });

    it("pinta el acento con el tint plano del modo (§3.5)", () => {
      const { container } = renderDisplay({
        modeId: "productividad",
        title: "Bloque de foco",
        staggerIndex: 0,
      });
      expect(accentOf(container)?.style.backgroundColor).toBe("var(--mode-productividad)");
    });

    it("una sugerencia transversal (mode null) lleva acento neutro", () => {
      const { container } = renderDisplay({
        modeId: null,
        title: "Pausá 10 min",
        subtitle: "Llevás 90 min en pantalla",
        staggerIndex: 1,
      });
      expect(screen.getByText("Pausá 10 min")).toBeInTheDocument();
      expect(accentOf(container)?.style.backgroundColor).toBe("var(--color-border-strong)");
    });
  });

  describe("variante accionable (con onClick)", () => {
    it("dispara onClick al tocarla", async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      render(<SuggestionCard modeId="estudio" title="Repasá el capítulo 3" onClick={onClick} />);
      await user.click(screen.getByRole("button"));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it("respeta disabled", async () => {
      const user = userEvent.setup();
      const onClick = vi.fn();
      render(
        <SuggestionCard modeId="estudio" title="Repasá el capítulo 3" onClick={onClick} disabled />,
      );
      await user.click(screen.getByRole("button"));
      expect(onClick).not.toHaveBeenCalled();
    });

    it("muestra el label del modo y pinta barra y dot con el tint plano", () => {
      const { container } = render(
        <SuggestionCard modeId="memoria" title="Retomá lo de ayer" onClick={() => {}} />,
      );
      expect(screen.getByText("Memoria")).toBeInTheDocument();
      const acentos = container.querySelectorAll<HTMLElement>("[aria-hidden]");
      expect(acentos).toHaveLength(2);
      for (const acento of acentos) {
        expect(acento.style.backgroundColor).toBe("var(--mode-memoria)");
      }
    });
  });
});
