import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Diamond } from "./Diamond";

describe("Diamond", () => {
  it("renderiza un elemento aria-hidden", () => {
    render(<Diamond />);
    // El span tiene aria-hidden, así que no es accesible por role — lo buscamos por el contenedor
    const el = document.querySelector("[aria-hidden='true']");
    expect(el).not.toBeNull();
  });

  it("aplica el tamaño recibido por props", () => {
    render(<Diamond size={16} />);
    const el = document.querySelector("[aria-hidden='true']") as HTMLElement;
    expect(el.style.width).toBe("16px");
    expect(el.style.height).toBe("16px");
  });

  it("aplica color como backgroundColor en variant solid", () => {
    render(<Diamond color="red" variant="solid" />);
    const el = document.querySelector("[aria-hidden='true']") as HTMLElement;
    expect(el.style.backgroundColor).toBe("red");
  });

  it("aplica border en variant outline", () => {
    render(<Diamond color="blue" variant="outline" />);
    const el = document.querySelector("[aria-hidden='true']") as HTMLElement;
    expect(el.style.border).toBeTruthy();
  });
});
