import { describe, expect, it } from "vitest";
import { buildMemoryList, searchMemoryList } from "./mocks";

const list = buildMemoryList(new Date("2026-06-01T12:00:00Z"));

describe("searchMemoryList", () => {
  it("matchea por substring case-insensitive sobre el contenido", () => {
    const hits = searchMemoryList(list, "TESIS");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits.every((h) => h.snippet.toLowerCase().includes("tesis"))).toBe(true);
  });

  it("devuelve vacío para query sin matches o vacía", () => {
    expect(searchMemoryList(list, "zxqw")).toEqual([]);
    expect(searchMemoryList(list, "   ")).toEqual([]);
  });

  it("asigna score decreciente dentro de 0..1", () => {
    const hits = searchMemoryList(list, "a"); // matchea varios
    expect(hits.length).toBeGreaterThan(1);
    for (const h of hits) {
      expect(h.score).toBeGreaterThanOrEqual(0.5);
      expect(h.score).toBeLessThanOrEqual(0.95);
    }
    // El primero no es menos relevante que el segundo.
    expect(hits[0]?.score ?? 0).toBeGreaterThanOrEqual(hits[1]?.score ?? 0);
  });

  it("matchea también sobre la capa procedural (key + value)", () => {
    const hits = searchMemoryList(list, "jerga");
    expect(hits.some((h) => h.layer === "procedural")).toBe(true);
  });
});
