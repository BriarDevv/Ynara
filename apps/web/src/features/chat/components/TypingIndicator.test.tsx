import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EmptyConversation } from "./EmptyConversation";
import { TypingIndicator } from "./TypingIndicator";

/**
 * Smoke tests: TypingIndicator + EmptyConversation con prompts sugeridos.
 */

describe("TypingIndicator", () => {
  it("renderiza con role=status y aria-label accesible", () => {
    render(<TypingIndicator modeId="vida" />);
    const indicator = screen.getByRole("status");
    expect(indicator).toHaveAttribute("aria-label", "Ynara está escribiendo");
  });

  it("renderiza los 3 puntos animados", () => {
    const { container } = render(<TypingIndicator modeId="estudio" />);
    // 3 spans con la clase anim-typing-dot
    const dots = container.querySelectorAll(".anim-typing-dot");
    expect(dots).toHaveLength(3);
  });

  it("el color de los puntos varía con el modeId", () => {
    const { container: c1 } = render(<TypingIndicator modeId="productividad" />);
    const { container: c2 } = render(<TypingIndicator modeId="bienestar" />);
    const dot1 = c1.querySelector(".anim-typing-dot") as HTMLElement;
    const dot2 = c2.querySelector(".anim-typing-dot") as HTMLElement;
    expect(dot1.style.backgroundColor).toContain("productividad");
    expect(dot2.style.backgroundColor).toContain("bienestar");
  });
});

describe("EmptyConversation — prompts sugeridos", () => {
  it("renderiza el título y la intro del modo", () => {
    render(<EmptyConversation mode="vida" onSend={vi.fn()} />);
    expect(screen.getByRole("heading", { name: /arranquemos/i })).toBeTruthy();
  });

  it("renderiza 4 prompts como botones accesibles", () => {
    render(<EmptyConversation mode="vida" onSend={vi.fn()} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(4);
  });

  it("click en un prompt llama onSend con el texto exacto", async () => {
    const onSend = vi.fn();
    render(<EmptyConversation mode="productividad" onSend={onSend} />);
    const [firstButton] = screen.getAllByRole("button");
    await userEvent.click(firstButton!);
    expect(onSend).toHaveBeenCalledOnce();
    expect(typeof onSend.mock.calls[0]?.[0]).toBe("string");
    expect((onSend.mock.calls[0]?.[0] as string).length).toBeGreaterThan(0);
  });

  it("la lista de prompts tiene aria-label accesible", () => {
    render(<EmptyConversation mode="estudio" onSend={vi.fn()} />);
    expect(screen.getByRole("list", { name: /prompts sugeridos/i })).toBeTruthy();
  });

  it("cada modo muestra prompts distintos (no comparte texto entre modos)", () => {
    const { unmount, getAllByRole: getVida } = (() => {
      const r = render(<EmptyConversation mode="vida" onSend={vi.fn()} />);
      return { ...r, getAllByRole: r.getAllByRole };
    })();
    const vidaTexts = getVida("button").map((b) => b.textContent);
    unmount();

    render(<EmptyConversation mode="estudio" onSend={vi.fn()} />);
    const estudioTexts = screen.getAllByRole("button").map((b) => b.textContent);

    const overlap = vidaTexts.filter((t) => estudioTexts.includes(t));
    expect(overlap).toHaveLength(0);
  });
});
