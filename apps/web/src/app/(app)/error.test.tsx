import { fireEvent, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const { default: AppError } = await import("./error");

describe("AppError (boundary del route group (app))", () => {
  it("muestra el fallback editorial con salida a /hoy y NO filtra el error crudo", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<AppError error={new Error("detalle sensible interno")} reset={() => {}} />);

    expect(
      screen.getByRole("heading", { name: /algo no salió como esperábamos/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /volver a hoy/i })).toHaveAttribute("href", "/hoy");
    // El mensaje crudo del error nunca se muestra al usuario (puede traer datos sensibles).
    expect(screen.queryByText(/detalle sensible interno/i)).not.toBeInTheDocument();
  });

  it("llama reset() al tocar Reintentar", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const reset = vi.fn();
    render(<AppError error={new Error("x")} reset={reset} />);

    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    expect(reset).toHaveBeenCalledTimes(1);
  });
});
