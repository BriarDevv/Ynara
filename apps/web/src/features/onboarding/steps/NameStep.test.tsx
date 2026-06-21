import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const { useOnboardingResumeStore } = await import("../resumeStore");
const { NameStep } = await import("./NameStep");

afterEach(() => {
  useOnboardingResumeStore.getState().setResuming(false);
});

describe("NameStep — back-guard del resume", () => {
  it("muestra 'Atrás' en el flujo normal de onboarding", () => {
    useOnboardingResumeStore.getState().setResuming(false);
    render(<NameStep />);
    expect(screen.getByRole("button", { name: /atrás/i })).toBeInTheDocument();
  });

  it("oculta 'Atrás' en resume (nombre es el piso, no se vuelve a auth)", () => {
    useOnboardingResumeStore.getState().setResuming(true);
    render(<NameStep />);
    expect(screen.queryByRole("button", { name: /atrás/i })).not.toBeInTheDocument();
  });
});
