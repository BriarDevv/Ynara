import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useUserStore } from "@/stores/user";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const { HoyEmptyState } = await import("./HoyEmptyState");

beforeEach(() => {
  push.mockClear();
  useUserStore.getState().setInterestedModes([]);
});

describe("HoyEmptyState", () => {
  it("muestra el estado vacío editorial de Hoy", () => {
    render(<HoyEmptyState />);
    expect(screen.getByRole("heading", { name: /tu día está despejado/i })).toBeInTheDocument();
  });

  it("el CTA lleva al chat", () => {
    render(<HoyEmptyState />);
    fireEvent.click(screen.getByRole("button", { name: /hablar con ynara/i }));
    expect(push).toHaveBeenCalledWith("/chat");
  });
});
