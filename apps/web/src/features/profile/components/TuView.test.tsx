import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

// Mockeamos todos los hooks que TuView consume, para aislar la vista de la
// infraestructura de red y TanStack Query (patrón de smoke test del proyecto).
vi.mock("@/features/profile/api", () => ({
  useUpdateMe: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    reset: vi.fn(),
  }),
}));

vi.mock("@/features/memory/api", () => ({
  useMemoryExport: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useMemoryWipePreview: () => ({
    mutateAsync: vi.fn().mockResolvedValue({ semantic: 3, episodic: 2, procedural: 2, total: 7 }),
    isPending: false,
    reset: vi.fn(),
  }),
  useMemoryWipeExecute: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    reset: vi.fn(),
    error: null,
  }),
}));

vi.mock("@/hooks/useActiveMode", () => ({
  useActiveMode: () => "productividad",
}));

vi.mock("@/stores/user", () => ({
  useUserStore: (selector: (s: unknown) => unknown) =>
    selector({
      displayName: "Mateo",
      interestedModes: ["productividad"],
      setDisplayName: vi.fn(),
      reset: vi.fn(),
    }),
}));

vi.mock("@/stores/a11y", () => ({
  useA11yStore: (selector: (s: unknown) => unknown) =>
    selector({
      textSize: "md",
      highContrast: false,
      motion: "auto",
      setTextSize: vi.fn(),
      setHighContrast: vi.fn(),
      setMotion: vi.fn(),
    }),
  applyA11yClasses: vi.fn(),
}));

// LivingField usa canvas + ResizeObserver: los mockeamos para jsdom.
vi.mock("@/components/ui/LivingField", () => ({
  LivingField: () => <div data-testid="living-field" />,
}));

// HeroReveal usa GSAP: mockeamos a un wrapper simple.
vi.mock("@/components/ui/HeroReveal", () => ({
  HeroReveal: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Cargamos el componente después de los mocks.
// biome-ignore lint/style/useImportType: se usa en JSX
import React from "react";
import { TuView } from "./TuView";

// jsdom no implementa showModal/close: stubs mínimos para Sheet.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});

describe("TuView — smoke", () => {
  it("renderiza el título principal", () => {
    render(<TuView />);
    expect(screen.getByRole("heading", { level: 1, name: "Tú" })).toBeInTheDocument();
  });

  it("muestra las secciones principales", () => {
    render(<TuView />);
    // h2 de cada SettingsSection
    expect(screen.getByRole("heading", { level: 2, name: "Perfil" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Retención de memoria sensible" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Memoria" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Accesibilidad" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Cuenta" })).toBeInTheDocument();
  });

  it("muestra el nombre del usuario en el campo de perfil", () => {
    render(<TuView />);
    const input = screen.getByRole("textbox", { name: /tu nombre/i });
    expect((input as HTMLInputElement).value).toBe("Mateo");
  });

  it("muestra el botón de cerrar sesión", () => {
    render(<TuView />);
    expect(screen.getByRole("button", { name: /cerrar sesión/i })).toBeInTheDocument();
  });

  it("muestra los links de memoria", () => {
    render(<TuView />);
    expect(screen.getByRole("link", { name: /ver mi memoria/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /buscar en mi memoria/i })).toBeInTheDocument();
  });

  it("muestra el botón destructivo de borrar memoria", () => {
    render(<TuView />);
    expect(screen.getByRole("button", { name: /borrar toda mi memoria/i })).toBeInTheDocument();
  });
});
