import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CheckinCta } from "./CheckinCta";

// Mañana (09:00) y noche (21:00) para chequear el saludo time-based.
const MORNING = new Date(2026, 0, 1, 9, 0);
const NIGHT = new Date(2026, 0, 1, 21, 0);

describe("CheckinCta", () => {
  it("renderiza el copy del check-in matinal", () => {
    render(<CheckinCta onOpen={() => {}} now={MORNING} />);
    expect(screen.getByText("¿Cómo arrancás hoy?")).toBeInTheDocument();
  });

  it("usa el saludo según la hora (no un texto fijo)", () => {
    // De noche saluda "Buenas noches" — antes hardcodeaba "Buenos días" y
    // contradecía al header de Hoy, que es time-based.
    render(<CheckinCta onOpen={() => {}} now={NIGHT} />);
    expect(screen.getByText("Buenas noches")).toBeInTheDocument();
    expect(screen.queryByText("Buenos días")).not.toBeInTheDocument();
  });

  it("a la mañana saluda 'Buen día'", () => {
    render(<CheckinCta onOpen={() => {}} now={MORNING} />);
    expect(screen.getByText("Buen día")).toBeInTheDocument();
  });

  it("dispara onOpen al click", () => {
    const onOpen = vi.fn();
    render(<CheckinCta onOpen={onOpen} now={MORNING} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
