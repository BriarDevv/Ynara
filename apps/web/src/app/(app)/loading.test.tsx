import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AppLoading from "./loading";

describe("AppLoading", () => {
  it("anuncia la carga con role=status (sin robar foco)", () => {
    render(<AppLoading />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Cargando");
  });
});
