import { describe, expect, it } from "vitest";

import { type LayoutInterval, layoutColumns } from "./layout";

/** Helper: arma un intervalo. */
const iv = (id: string, start: number, end: number): LayoutInterval => ({ id, start, end });

describe("layoutColumns", () => {
  it("devuelve un mapa vacío sin eventos", () => {
    expect(layoutColumns([]).size).toBe(0);
  });

  it("un solo evento ocupa el ancho completo", () => {
    const out = layoutColumns([iv("a", 0, 60)]);
    expect(out.get("a")).toEqual({ col: 0, cols: 1 });
  });

  it("eventos que no se solapan comparten columna (cada uno ancho completo)", () => {
    const out = layoutColumns([iv("a", 0, 60), iv("b", 60, 120), iv("c", 120, 180)]);
    expect(out.get("a")).toEqual({ col: 0, cols: 1 });
    expect(out.get("b")).toEqual({ col: 0, cols: 1 });
    expect(out.get("c")).toEqual({ col: 0, cols: 1 });
  });

  it("dos eventos solapados van a 2 columnas", () => {
    const out = layoutColumns([iv("a", 0, 90), iv("b", 30, 120)]);
    expect(out.get("a")).toEqual({ col: 0, cols: 2 });
    expect(out.get("b")).toEqual({ col: 1, cols: 2 });
  });

  it("solapamiento transitivo: A∩B, B∩C, A∌C → un cluster de 2 columnas, C reusa col 0", () => {
    // A[0,60] ∩ B[30,90] ∩ C[80,120]; A y C no se tocan.
    const out = layoutColumns([iv("a", 0, 60), iv("b", 30, 90), iv("c", 80, 120)]);
    expect(out.get("a")).toEqual({ col: 0, cols: 2 });
    expect(out.get("b")).toEqual({ col: 1, cols: 2 });
    // C arranca en 80 >= fin de A (60) → reusa la columna 0; mismo cluster que A/B.
    expect(out.get("c")).toEqual({ col: 0, cols: 2 });
  });

  it("eventos que apenas se tocan (end === start) NO se solapan", () => {
    const out = layoutColumns([iv("a", 0, 60), iv("b", 60, 120)]);
    expect(out.get("a")).toEqual({ col: 0, cols: 1 });
    expect(out.get("b")).toEqual({ col: 0, cols: 1 });
  });

  it("tres eventos todos solapados → 3 columnas", () => {
    const out = layoutColumns([iv("a", 0, 90), iv("b", 10, 80), iv("c", 20, 70)]);
    expect(out.get("a")).toEqual({ col: 0, cols: 3 });
    expect(out.get("b")).toEqual({ col: 1, cols: 3 });
    expect(out.get("c")).toEqual({ col: 2, cols: 3 });
  });

  it("a igual inicio, el más largo agarra la primera columna", () => {
    const out = layoutColumns([iv("short", 0, 30), iv("long", 0, 120)]);
    expect(out.get("long")).toEqual({ col: 0, cols: 2 });
    expect(out.get("short")).toEqual({ col: 1, cols: 2 });
  });

  it("clusters independientes se cuentan por separado", () => {
    // Cluster 1: a∩b (2 col). Cluster 2: c solo (1 col).
    const out = layoutColumns([iv("a", 0, 60), iv("b", 30, 90), iv("c", 200, 260)]);
    expect(out.get("a")).toEqual({ col: 0, cols: 2 });
    expect(out.get("b")).toEqual({ col: 1, cols: 2 });
    expect(out.get("c")).toEqual({ col: 0, cols: 1 });
  });

  it("no muta el array de entrada (orden preservado)", () => {
    const input = [iv("a", 100, 160), iv("b", 0, 60)];
    const snapshot = input.map((e) => e.id);
    layoutColumns(input);
    expect(input.map((e) => e.id)).toEqual(snapshot);
  });
});
