import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RecapCta } from "./RecapCta";

describe("RecapCta", () => {
  it("muestra el copy del recap pendiente", () => {
    render(<RecapCta onOpen={vi.fn()} />);
    expect(screen.getByText("Recap pendiente")).toBeInTheDocument();
    expect(screen.getByText("Cerrá el día con Ynara")).toBeInTheDocument();
  });

  it("dispara onOpen al clickear", () => {
    const onOpen = vi.fn();
    render(<RecapCta onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalledOnce();
  });
});
