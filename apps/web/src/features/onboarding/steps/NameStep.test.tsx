import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const { NameStep } = await import("./NameStep");

describe("NameStep", () => {
  it("muestra 'Atrás' para volver al paso anterior", () => {
    render(<NameStep />);
    expect(screen.getByRole("button", { name: /atrás/i })).toBeInTheDocument();
  });
});
