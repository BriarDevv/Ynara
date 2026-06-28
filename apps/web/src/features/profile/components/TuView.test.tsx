import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

// Mock mutable de useUpdateMe (vi.hoisted) para poder variar mutateAsync por
// test (p. ej. rechazar el PATCH y verificar el revert de la retención).
const updateMe = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
  reset: vi.fn(),
}));
// Mock mutable de useMe (G3): por defecto sin data (la retención arranca en el
// default 365); los tests que ejercitan la hidratación setean `meQuery.data`.
const meQuery = vi.hoisted(() => ({
  data: undefined as { retention_sensitive_days: number } | undefined,
}));
vi.mock("@/features/profile/api", () => ({
  useUpdateMe: () => updateMe,
  useMe: () => meQuery,
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
      token: "t1",
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

vi.mock("@/stores/theme", () => ({
  useThemeStore: (selector: (s: unknown) => unknown) =>
    selector({
      theme: "dark",
      setTheme: vi.fn(),
      toggleTheme: vi.fn(),
      reset: vi.fn(),
    }),
  applyThemeClass: vi.fn(),
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

// TuView usa `useQueryClient` (logout total limpia la cache): envolvemos en un
// QueryClientProvider real. Las mutations de red siguen mockeadas arriba.
function renderTuView() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <TuView />
    </QueryClientProvider>,
  );
}

describe("TuView — smoke", () => {
  beforeEach(() => {
    // Reset entre tests: por defecto el PATCH resuelve (los tests que quieren
    // fallo lo sobrescriben) y `me` sin data (retención en el default 365).
    updateMe.mutateAsync = vi.fn().mockResolvedValue({ display_name: "Mateo" });
    meQuery.data = undefined;
  });

  it("renderiza el nombre del usuario como heading principal", () => {
    renderTuView();
    expect(screen.getByRole("heading", { level: 1, name: "Mateo" })).toBeInTheDocument();
  });

  it("muestra el avatar con la inicial del nombre", () => {
    renderTuView();
    expect(screen.getByRole("img", { name: /avatar de mateo/i })).toBeInTheDocument();
  });

  it("muestra el badge de plan", () => {
    renderTuView();
    expect(screen.getByText(/plan gratis/i)).toBeInTheDocument();
  });

  it("muestra el campo de nombre con el valor del usuario", () => {
    renderTuView();
    const input = screen.getByRole("textbox", { name: /tu nombre/i });
    expect((input as HTMLInputElement).value).toBe("Mateo");
  });

  it("muestra los links de memoria", () => {
    renderTuView();
    expect(screen.getByRole("link", { name: /tu memoria/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /buscar/i })).toBeInTheDocument();
  });

  it("muestra el botón destructivo de borrar memoria", () => {
    renderTuView();
    expect(screen.getByRole("button", { name: /borrar toda mi memoria/i })).toBeInTheDocument();
  });

  it("muestra el botón de cerrar sesión", () => {
    renderTuView();
    expect(screen.getByRole("button", { name: /cerrar sesión/i })).toBeInTheDocument();
  });

  it("muestra el selector de tema Claro/Oscuro", () => {
    renderTuView();
    // ChipGroup de tema renderiza opciones como radio/button
    expect(screen.getByText(/claro/i)).toBeInTheDocument();
    expect(screen.getByText(/oscuro/i)).toBeInTheDocument();
  });

  it("muestra el footer con versión y tagline", () => {
    renderTuView();
    expect(screen.getByText(/ynara · mvp 2026/i)).toBeInTheDocument();
    expect(screen.getByText(/pensar mejor, recordar siempre/i)).toBeInTheDocument();
  });

  it("muestra el botón de exportar memoria", () => {
    renderTuView();
    expect(screen.getByRole("button", { name: /exportar mi memoria/i })).toBeInTheDocument();
  });

  it("hidrata la retención con el valor real del backend (me)", async () => {
    // G3: `me` trae la retención persistida → el chip arranca en ese valor, no en
    // el default 365.
    meQuery.data = { retention_sensitive_days: 90 };
    renderTuView();
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /90 días/i })).toHaveAttribute(
        "aria-checked",
        "true",
      ),
    );
    expect(screen.getByRole("radio", { name: /1 año/i })).toHaveAttribute("aria-checked", "false");
  });

  it("revierte la retención al valor previo si el PATCH falla", async () => {
    updateMe.mutateAsync = vi.fn().mockRejectedValue(new Error("boom"));
    renderTuView();
    // Default: "1 año" (365) seleccionado.
    expect(screen.getByRole("radio", { name: /1 año/i })).toHaveAttribute("aria-checked", "true");

    fireEvent.click(screen.getByRole("radio", { name: /30 días/i }));

    // El server rechaza → vuelve a 365, no queda en 30 (no miente sobre la retención).
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /1 año/i })).toHaveAttribute("aria-checked", "true"),
    );
    expect(screen.getByRole("radio", { name: /30 días/i })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });
});
