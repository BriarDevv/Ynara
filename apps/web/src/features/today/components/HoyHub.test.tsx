import { render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// `buildAnticipations()` (vía HoyHub) gatea su data demo por `shouldEnableMocks`
// (features/today/anticipations.ts). En CI los tests corren con
// NEXT_PUBLIC_ENABLE_MOCKS=false → sin este mock devolvería [] y los asserts del
// badge ("N pendientes") fallarían. Forzamos el flag para que este test del badge
// del acceso a Avisos sea determinista e independiente del entorno de mocks.
vi.mock("@/lib/env", async () => {
  const actual = await vi.importActual<typeof import("@/lib/env")>("@/lib/env");
  return { ...actual, shouldEnableMocks: true };
});

const { useAvisosStore } = await import("../avisosStore");
const { HoyHub } = await import("./HoyHub");

beforeEach(() => {
  useAvisosStore.getState().reset();
});

describe("HoyHub", () => {
  it("linkea a Memoria, Avisos y Buscar", () => {
    render(<HoyHub />);
    expect(screen.getByRole("link", { name: /tu memoria/i })).toHaveAttribute("href", "/memoria");
    expect(screen.getByRole("link", { name: /avisos/i })).toHaveAttribute("href", "/avisos");
    expect(screen.getByRole("link", { name: /buscar/i })).toHaveAttribute("href", "/buscar");
  });

  it("el acceso a Avisos expone los pendientes en el nombre accesible", () => {
    render(<HoyHub />);
    // Sin resolver nada, hay 4 anticipaciones canned pendientes.
    expect(screen.getByRole("link", { name: /avisos — 4 pendientes/i })).toBeInTheDocument();
  });

  it("resolver avisos baja el contador del acceso", () => {
    useAvisosStore.getState().resolve("ant-foco-001");
    render(<HoyHub />);
    expect(screen.getByRole("link", { name: /avisos — 3 pendientes/i })).toBeInTheDocument();
  });

  it("sin pendientes, el acceso a Avisos cae al nombre simple (sin badge)", () => {
    for (const id of ["ant-foco-001", "ant-pausa-001", "ant-estudio-001", "ant-vida-001"]) {
      useAvisosStore.getState().resolve(id);
    }
    render(<HoyHub />);
    expect(screen.getByRole("link", { name: "Avisos" })).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });
});
