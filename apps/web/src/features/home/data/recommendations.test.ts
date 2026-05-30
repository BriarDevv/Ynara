import { describe, expect, it } from "vitest";
import type { ModeId } from "@/components/ui/modes";
import { pickRecommendations, RECOMMENDATIONS, type Recommendation } from "./recommendations";

/** Catálogo de prueba con cantidades controladas por modo. */
const CATALOG: readonly Recommendation[] = [
  rec("prod-1", "productividad"),
  rec("prod-2", "productividad"),
  rec("prod-3", "productividad"),
  rec("est-1", "estudio"),
  rec("est-2", "estudio"),
  rec("bien-1", "bienestar"),
  rec("mem-1", "memoria"),
];

function rec(id: string, modeId: ModeId): Recommendation {
  return { id, title: id, subtitle: "", modeId, prefillPrompt: "" };
}

function ids(list: Recommendation[]): string[] {
  return list.map((r) => r.id);
}

describe("pickRecommendations", () => {
  it("sin modos de interés cae a las primeras `limit` del catálogo", () => {
    const result = pickRecommendations([], 4, CATALOG);
    expect(ids(result)).toEqual(["prod-1", "prod-2", "prod-3", "est-1"]);
  });

  it("con 1 modo devuelve hasta `limit` cards de ese modo", () => {
    const result = pickRecommendations(["productividad"], 4, CATALOG);
    expect(ids(result)).toEqual(["prod-1", "prod-2", "prod-3"]);
    expect(result.every((r) => r.modeId === "productividad")).toBe(true);
  });

  it("con 2+ modos toma 1 card por modo en orden y luego rellena el cupo", () => {
    const result = pickRecommendations(["estudio", "productividad"], 4, CATALOG);
    // Primera pasada: est-1, prod-1. Segunda pasada (relleno): est-2, prod-2.
    expect(ids(result)).toEqual(["est-1", "prod-1", "est-2", "prod-2"]);
  });

  it("respeta el orden de interés en la primera pasada", () => {
    const result = pickRecommendations(["memoria", "bienestar"], 2, CATALOG);
    expect(ids(result)).toEqual(["mem-1", "bien-1"]);
  });

  it("nunca devuelve duplicados", () => {
    const result = pickRecommendations(["productividad", "productividad", "estudio"], 6, CATALOG);
    expect(new Set(ids(result)).size).toBe(result.length);
  });

  it("respeta el `limit` aunque haya más cards disponibles", () => {
    const result = pickRecommendations(["productividad", "estudio"], 2, CATALOG);
    expect(result).toHaveLength(2);
    expect(ids(result)).toEqual(["prod-1", "est-1"]);
  });

  it("no excede la cantidad de cards existentes para los modos pedidos", () => {
    const result = pickRecommendations(["bienestar"], 4, CATALOG);
    expect(ids(result)).toEqual(["bien-1"]);
  });

  it("usa el catálogo real por default y respeta el limit por default de 4", () => {
    const result = pickRecommendations(["productividad"]);
    expect(result.length).toBeLessThanOrEqual(4);
    expect(result.every((r) => RECOMMENDATIONS.some((c) => c.id === r.id))).toBe(true);
  });
});
