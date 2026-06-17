import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CheckinCta } from "./CheckinCta";

describe("CheckinCta", () => {
  it("renderiza el copy del check-in matinal", () => {
    render(<CheckinCta onOpen={() => {}} />);
    expect(screen.getByText("¿Cómo arrancás hoy?")).toBeInTheDocument();
  });

  it("dispara onOpen al click", () => {
    const onOpen = vi.fn();
    render(<CheckinCta onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
