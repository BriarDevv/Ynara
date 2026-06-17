import { render, screen, within } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useThemeStore } from "@/stores/theme";
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
const { MobileTabBar, SidebarNav } = await import("./AppNav");

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

describe("MobileTabBar", () => {
  it("renderiza las 4 tabs", () => {
    mockPathname = "/hoy";
    render(<MobileTabBar />);
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(within(nav).getByRole("link", { name: "Hoy" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Chat" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Agenda" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Tú" })).toBeInTheDocument();
  });

  it("marca aria-current='page' sólo en la tab activa", () => {
    mockPathname = "/chat/sesion-1";
    render(<MobileTabBar />);
    expect(screen.getByRole("link", { name: "Chat" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Hoy" })).not.toHaveAttribute("aria-current");
  });
});

describe("SidebarNav", () => {
  // El store de tema es singleton de módulo: resetear para no arrastrar el
  // "dark" que persisten otros archivos (theme.test.ts) y aislar las ramas.
  afterEach(() => {
    useThemeStore.getState().reset();
    localStorage.clear();
  });

  it("renderiza el lockup + las 4 tabs y marca la activa", () => {
    mockPathname = "/agenda";
    render(<SidebarNav />);
    expect(screen.getByRole("link", { name: "Ynara — ir a Hoy" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Agenda" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Tú" })).not.toHaveAttribute("aria-current");
  });

  it("en claro monta el wordmark a color (símbolo con gradiente)", () => {
    mockPathname = "/hoy";
    useThemeStore.getState().setTheme("light");
    const { container } = render(<SidebarNav />);
    const lockup = screen.getByRole("link", { name: "Ynara — ir a Hoy" });
    expect(within(lockup).getByRole("img", { name: "Ynara" })).toBeInTheDocument();
    expect(container.querySelector("linearGradient")).toBeInTheDocument();
    // Isotipo oficial → gradiente con el azul de marca (#305ba6).
    expect(container.innerHTML).toContain("#305ba6");
  });

  it("en Noche monta el wordmark mono-light (silueta marfil, sin gradiente)", () => {
    mockPathname = "/hoy";
    useThemeStore.getState().setTheme("dark");
    const { container } = render(<SidebarNav />);
    // Tras montar (useEffect), la variante pasa a mono-light.
    expect(container.innerHTML).toContain("var(--color-marfil");
    expect(container.querySelector("linearGradient")).not.toBeInTheDocument();
  });
});
