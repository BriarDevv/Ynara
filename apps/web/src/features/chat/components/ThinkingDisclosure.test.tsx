import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ThinkingDisclosure } from "./ThinkingDisclosure";

describe("ThinkingDisclosure", () => {
  it("arranca abierto mientras el modelo piensa (streaming sin respuesta)", () => {
    render(<ThinkingDisclosure reasoning="analizando…" streaming />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  });

  it("arranca colapsado cuando ya hay respuesta (streaming false)", () => {
    render(<ThinkingDisclosure reasoning="analizando…" streaming={false} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
  });

  it("auto-colapsa cuando la respuesta llega (streaming true → false)", () => {
    const { rerender } = render(<ThinkingDisclosure reasoning="raz" streaming />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");

    rerender(<ThinkingDisclosure reasoning="raz" streaming={false} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
  });

  it("es re-expandible: el click reabre el colapsado", async () => {
    const user = userEvent.setup();
    render(<ThinkingDisclosure reasoning="raz" streaming={false} />);

    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-expanded", "false");
    await user.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });

  it("renderiza el razonamiento como texto plano (no markdown)", () => {
    render(<ThinkingDisclosure reasoning="paso **uno** y dos" streaming />);
    // Los asteriscos quedan literales: no se interpretan como markdown.
    expect(screen.getByText("paso **uno** y dos")).toBeInTheDocument();
  });
});
