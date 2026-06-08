import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StepShell } from "./StepShell";

// StepShell es un container presentacional puro — no usa hooks de framework
// ni store. Verificamos que la jerarquía editorial del lenguaje sobrio se
// respete: h1 con `--color-ink-deep`, subtítulo con `--color-ink-soft`, y
// que los slots opcionales (eyebrow, subtitle, footer) sólo monten cuando
// se pasan.

describe("StepShell", () => {
  it("renderiza el title como h1 con la tinta editorial del lenguaje sobrio", () => {
    render(
      <StepShell title="Antes que nada">
        <p>Contenido del step</p>
      </StepShell>,
    );

    const heading = screen.getByRole("heading", { level: 1, name: "Antes que nada" });
    expect(heading.className).toContain("text-[var(--color-ink-deep)]");
    expect(heading.className).toContain("text-title");
  });

  it("renderiza el subtitle con ink-soft cuando se pasa", () => {
    render(
      <StepShell title="Título" subtitle="Subtítulo del step">
        <p>Body</p>
      </StepShell>,
    );

    const sub = screen.getByText("Subtítulo del step");
    expect(sub.className).toContain("text-[var(--color-ink-soft)]");
    expect(sub.className).toContain("text-body");
  });

  it("omite el subtitle si no se pasa la prop", () => {
    render(
      <StepShell title="Solo título">
        <p>Body</p>
      </StepShell>,
    );

    // El header sólo debería tener el h1, sin párrafos hermanos.
    const heading = screen.getByRole("heading", { level: 1 });
    const header = heading.parentElement as HTMLElement;
    expect(header.querySelectorAll("p").length).toBe(0);
  });

  it("renderiza el eyebrow opcional como caption ink-soft encima del title", () => {
    render(
      <StepShell eyebrow="Paso 1 — Mood" title="¿Cómo viene tu día?">
        <p>Body</p>
      </StepShell>,
    );

    const eyebrow = screen.getByText("Paso 1 — Mood");
    expect(eyebrow.className).toContain("text-caption");
    // ink-soft (no muted): el eyebrow es TEXTO y debe pasar AA (PR #11, QA de
    // contraste). ink-muted (~2.6:1) queda solo para decoración / íconos
    // aria-hidden (exentos de WCAG 1.4.11).
    expect(eyebrow.className).toContain("text-[var(--color-ink-soft)]");

    // El eyebrow debe estar antes del h1 dentro del mismo header.
    const heading = screen.getByRole("heading", { level: 1 });
    const header = heading.parentElement as HTMLElement;
    const children = Array.from(header.children);
    expect(children.indexOf(eyebrow)).toBeLessThan(children.indexOf(heading));
  });

  it("renderiza children en el body", () => {
    render(
      <StepShell title="T">
        <p data-testid="body-content">Cuerpo del step</p>
      </StepShell>,
    );

    expect(screen.getByTestId("body-content")).toBeDefined();
  });

  it("renderiza el footer slot cuando se pasa", () => {
    render(
      <StepShell
        title="T"
        footer={
          <button type="button" data-testid="step-footer">
            Siguiente
          </button>
        }
      >
        <p>Body</p>
      </StepShell>,
    );

    expect(screen.getByTestId("step-footer")).toBeDefined();
  });

  it("no monta el contenedor del footer si no se pasa la prop", () => {
    const { container } = render(
      <StepShell title="T">
        <p>Body</p>
      </StepShell>,
    );

    // El footer es el último hijo directo del root cuando existe; verificamos
    // que el root tenga sólo header + body (2 hijos), no 3.
    const root = container.firstElementChild as HTMLElement;
    expect(root.children.length).toBe(2);
  });

  it("acumula className extra del caller sobre el wrapper", () => {
    const { container } = render(
      <StepShell title="T" className="custom-class-x">
        <p>Body</p>
      </StepShell>,
    );

    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("custom-class-x");
    // También mantiene las clases base del lenguaje sobrio (anim-fade-up).
    expect(root.className).toContain("anim-fade-up");
  });
});
