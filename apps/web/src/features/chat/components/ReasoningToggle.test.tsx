import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useShowReasoningStore } from "@/stores/showReasoning";
import { ReasoningToggle } from "./ReasoningToggle";

describe("ReasoningToggle", () => {
  beforeEach(() => {
    useShowReasoningStore.getState().reset();
    localStorage.clear();
  });

  afterEach(() => {
    useShowReasoningStore.getState().reset();
    localStorage.clear();
  });

  it("arranca apagado (aria-checked false, espejo del default OFF)", () => {
    render(<ReasoningToggle />);
    expect(screen.getByTestId("toggle-reasoning")).toHaveAttribute("aria-checked", "false");
  });

  it("el click prende el razonamiento en el store y refleja aria-checked", async () => {
    const user = userEvent.setup();
    render(<ReasoningToggle />);

    await user.click(screen.getByTestId("toggle-reasoning"));

    expect(useShowReasoningStore.getState().enabled).toBe(true);
    expect(screen.getByTestId("toggle-reasoning")).toHaveAttribute("aria-checked", "true");
  });
});
