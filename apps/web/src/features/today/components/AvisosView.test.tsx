import { fireEvent, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAvisosStore } from "../avisosStore";

// next/link → <a> plano para jsdom.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// Mocks de infraestructura de UI (canvas / GSAP / animaciones).
vi.mock("@/components/ui/LivingField", () => ({
  LivingField: () => null,
}));
vi.mock("@/components/ui/HeroReveal", () => ({
  HeroReveal: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
}));

// useActiveMode: devuelve un modo estable.
vi.mock("@/hooks/useActiveMode", () => ({
  useActiveMode: () => "productividad" as const,
}));

// buildAnticipations: dos avisos mock para el smoke.
vi.mock("../anticipations", () => ({
  buildAnticipations: () => [
    {
      id: "aviso-test-001",
      kind: "Anticipación",
      time: "10:30",
      text: "Aviso de prueba uno",
      mode: "productividad",
      actions: [{ label: "Aceptar", primary: true }, { label: "Ignorar" }],
    },
    {
      id: "aviso-test-002",
      kind: "Recordatorio",
      time: "12:00",
      text: "Aviso de prueba dos",
      mode: "bienestar",
      actions: [{ label: "Listo", primary: true }, { label: "Más tarde" }],
    },
  ],
}));

const { AvisosView } = await import("./AvisosView");

describe("AvisosView", () => {
  // El estado de avisos resueltos es un store compartido (singleton): reset
  // entre tests para que resolver en uno no filtre al siguiente.
  beforeEach(() => {
    useAvisosStore.getState().reset();
  });

  it("muestra el header 'Avisos' y el subline con pendientes", () => {
    render(<AvisosView />);
    expect(screen.getByRole("heading", { name: "Avisos" })).toBeInTheDocument();
    expect(screen.getByText(/Ynara se adelanta/)).toBeInTheDocument();
    expect(screen.getByText(/2 cosas para hoy/)).toBeInTheDocument();
  });

  it("renderiza los avisos activos en la sección", () => {
    render(<AvisosView />);
    expect(screen.getByText("Aviso de prueba uno")).toBeInTheDocument();
    expect(screen.getByText("Aviso de prueba dos")).toBeInTheDocument();
  });

  it("al resolver un aviso, aparece en Resueltos y desaparece de activos", () => {
    render(<AvisosView />);
    // El primer aviso tiene el botón "Aceptar" (primary).
    fireEvent.click(screen.getByRole("button", { name: "Aceptar" }));

    // La sección Resueltos aparece con el texto calmo.
    expect(screen.getByText("Listo. Lo dejé resuelto por vos.")).toBeInTheDocument();
    // El aviso ya no está en activos (el texto principal desapareció).
    expect(screen.queryByText("Aviso de prueba uno")).not.toBeInTheDocument();
  });

  it("cuando todos los avisos se resuelven, el subline dice 'Todo al día.'", () => {
    render(<AvisosView />);
    fireEvent.click(screen.getByRole("button", { name: "Aceptar" }));
    fireEvent.click(screen.getByRole("button", { name: "Listo" }));
    expect(screen.getByText("Todo al día.")).toBeInTheDocument();
  });

  it("muestra la nota de Premium al pie", () => {
    render(<AvisosView />);
    expect(screen.getByText(/premium suma anticipaciones ilimitadas/i)).toBeInTheDocument();
  });

  it("la sección activa tiene aria-live='polite'", () => {
    render(<AvisosView />);
    expect(screen.getByRole("region", { name: "Avisos activos" })).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });
});
