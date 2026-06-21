import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const mutateAsync = vi.fn();
vi.mock("../api", () => ({
  useCreateEvent: () => ({ mutateAsync, isPending: false }),
}));

// jsdom no implementa showModal/close del <dialog> (Sheet).
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false;
  };
});

const { EventFab } = await import("./EventFab");

beforeEach(() => {
  mutateAsync.mockReset();
});

function openSheet() {
  render(<EventFab fillVar="var(--mode-productividad-fill)" activeMode="productividad" />);
  fireEvent.click(screen.getByRole("button", { name: /crear evento/i }));
}

describe("EventFab", () => {
  it("título vacío marca el campo (aria-invalid) y no crea el evento", () => {
    openSheet();
    fireEvent.click(screen.getByRole("button", { name: /^crear$/i }));

    const title = screen.getByRole("textbox", { name: /título/i });
    expect(title).toHaveAttribute("aria-invalid", "true");
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("con título válido crea el evento", () => {
    mutateAsync.mockResolvedValue({});
    openSheet();
    fireEvent.change(screen.getByRole("textbox", { name: /título/i }), {
      target: { value: "Reunión con cátedra" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^crear$/i }));

    expect(mutateAsync).toHaveBeenCalledTimes(1);
    expect(mutateAsync.mock.calls[0]?.[0]).toMatchObject({
      title: "Reunión con cátedra",
      mode: "productividad",
    });
  });
});
