import { render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { describe, expect, it, vi } from "vitest";
import { isNavItemActive } from "./nav-items";

// Pathname controlable por test. El prefijo `mock` lo habilita dentro del
// factory hoisteado de vi.mock.
let mockPathname = "/hoy";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));
// next/link → <a> plano: en jsdom no necesitamos el router context real.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// Import después de los mocks.
const { AppNav } = await import("./AppNav");

describe("isNavItemActive", () => {
  it("matchea la ruta exacta", () => {
    expect(isNavItemActive("/hoy", "/hoy")).toBe(true);
  });

  it("matchea sub-rutas que cuelgan del href", () => {
    expect(isNavItemActive("/chat/abc-123", "/chat")).toBe(true);
  });

  it("no matchea prefijos que no son segmento de ruta", () => {
    // /hoyx no debe activar /hoy.
    expect(isNavItemActive("/hoyx", "/hoy")).toBe(false);
  });

  it("no matchea rutas ajenas", () => {
    expect(isNavItemActive("/agenda", "/hoy")).toBe(false);
  });
});

describe("AppNav", () => {
  it("renderiza las 4 tabs en los dos chrome (bottom-tabs + sidebar)", () => {
    mockPathname = "/hoy";
    render(<AppNav />);
    // Dos <nav> (mobile + desktop), ambos en el DOM (jsdom no aplica el
    // display:none de Tailwind): 2 links por tab.
    expect(screen.getAllByRole("link", { name: "Hoy" })).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: "Agenda" })).toHaveLength(2);
  });

  it("marca aria-current='page' sólo en la tab activa", () => {
    mockPathname = "/chat/sesion-1";
    render(<AppNav />);
    for (const link of screen.getAllByRole("link", { name: "Chat" })) {
      expect(link).toHaveAttribute("aria-current", "page");
    }
    for (const link of screen.getAllByRole("link", { name: "Hoy" })) {
      expect(link).not.toHaveAttribute("aria-current");
    }
  });
});
