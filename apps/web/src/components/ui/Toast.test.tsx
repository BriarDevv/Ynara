import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toast } from "./Toast";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

describe("Toast", () => {
  it("visible entra con la animación de entrada", () => {
    render(<Toast message="Guardado" visible onDismiss={() => {}} duration={0} />);
    const box = screen.getByText("Guardado").parentElement as HTMLElement;
    expect(box.className).toContain("anim-toast-in");
  });

  it("auto-dismiss llama onDismiss tras la duración", () => {
    const onDismiss = vi.fn();
    render(<Toast message="Hola" visible onDismiss={onDismiss} duration={3000} />);
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("al ocultar, anima la salida y desmonta recién después de 200ms", () => {
    const { rerender } = render(<Toast message="Chau" visible onDismiss={() => {}} duration={0} />);
    expect(screen.getByText("Chau")).toBeDefined();

    rerender(<Toast message="Chau" visible={false} onDismiss={() => {}} duration={0} />);
    // sigue montado, ahora con la animación de salida
    const box = screen.getByText("Chau").parentElement as HTMLElement;
    expect(box.className).toContain("anim-toast-out");

    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.queryByText("Chau")).toBeNull();
  });

  it("no renderiza nada si nunca fue visible", () => {
    render(<Toast message="Invisible" visible={false} onDismiss={() => {}} />);
    expect(screen.queryByText("Invisible")).toBeNull();
  });
});
