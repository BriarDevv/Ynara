import { render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { describe, expect, it, vi } from "vitest";

// next/link → <a> plano: en jsdom no hace falta el router context real.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const { default: NotFound } = await import("./not-found");

describe("NotFound (404 raíz)", () => {
  it("muestra el mensaje editorial y un link de vuelta a /hoy", () => {
    render(<NotFound />);
    expect(
      screen.getByRole("heading", { name: /no encontramos esta página/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /volver a hoy/i })).toHaveAttribute("href", "/hoy");
  });
});
