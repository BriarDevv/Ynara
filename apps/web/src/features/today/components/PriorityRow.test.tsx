import { fireEvent, render, screen } from "@testing-library/react";
import type { Task } from "@ynara/shared-schemas";
import { describe, expect, it, vi } from "vitest";
import { PriorityRow } from "./PriorityRow";

const at = (h: number, m: number) => new Date(2026, 4, 7, h, m).toISOString();

const pending: Task = {
  id: "0193c001-0000-4000-8000-000000000002",
  title: "Llamada con equipo de diseño",
  status: "pending",
  scheduled_at: at(14, 0),
  duration_min: 45,
};

const done: Task = { ...pending, status: "done", scheduled_at: at(9, 15), duration_min: null };

function renderRow(task: Task, onToggle = vi.fn()) {
  render(
    <ul>
      <PriorityRow task={task} index={0} onToggle={onToggle} />
    </ul>,
  );
  return onToggle;
}

describe("PriorityRow", () => {
  it("muestra el título y la meta de una tarea pendiente", () => {
    renderRow(pending);
    expect(screen.getByText("Llamada con equipo de diseño")).toBeInTheDocument();
    expect(screen.getByText("14:00 · 45 min")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).toHaveAttribute("aria-checked", "false");
  });

  it("una tarea hecha marca el checkbox y muestra 'completada'", () => {
    renderRow(done);
    expect(screen.getByText("09:15 · completada")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).toHaveAttribute("aria-checked", "true");
  });

  it("clickear el check dispara onToggle con la tarea", () => {
    const onToggle = renderRow(pending);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onToggle).toHaveBeenCalledWith(pending);
  });
});
