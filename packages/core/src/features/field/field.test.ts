import { describe, expect, it } from "vitest";
import {
  advanceTime,
  breath,
  buildBlooms,
  buildWaves,
  diamondCount,
  MODE_CLIMATE,
  nodeCount,
  RIBBONS,
  repel,
  ribbonEdgeY,
  seedField,
  stepNodes,
  THREADS,
} from "./index";

// RNG determinístico (LCG) para sembrar campos reproducibles en el test.
function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

describe("field/config", () => {
  it("nodeCount está acotado [10, 130]", () => {
    expect(nodeCount(1, 1, 1)).toBe(10); // mínimo
    expect(nodeCount(10000, 10000, 2)).toBe(130); // cap duro
    expect(nodeCount(800, 600, 1)).toBe(Math.round((800 * 600) / 12500));
  });

  it("diamondCount ~12% de los nodos, mínimo 2", () => {
    expect(diamondCount(1)).toBe(2);
    expect(diamondCount(100)).toBe(12);
  });

  it("MODE_CLIMATE tiene los 5 modos con pares hex", () => {
    expect(Object.keys(MODE_CLIMATE)).toHaveLength(5);
    expect(MODE_CLIMATE.productividad).toEqual({ a: "#2f5aa6", b: "#6e92cc" });
    expect(MODE_CLIMATE.memoria).toEqual({ a: "#6e92cc", b: "#8b9ad0" });
  });
});

describe("field/model", () => {
  it("seedField sin partículas → vacío", () => {
    expect(seedField(800, 600, 1, false)).toEqual({ nodes: [], diamonds: [] });
  });

  it("seedField con el mismo RNG es reproducible y respeta el conteo", () => {
    const a = seedField(800, 600, 1, true, lcg(42));
    const b = seedField(800, 600, 1, true, lcg(42));
    expect(a.nodes).toHaveLength(nodeCount(800, 600, 1));
    expect(a.diamonds).toHaveLength(diamondCount(a.nodes.length));
    expect(a.nodes[0]).toEqual(b.nodes[0]); // determinístico con misma semilla
  });

  it("advanceTime y breath", () => {
    expect(advanceTime(0, 1)).toBeCloseTo(0.0045);
    expect(breath(0)).toBeCloseTo(0.62); // sin(0) = 0
  });

  it("stepNodes hace wrap en los bordes", () => {
    const nodes = [
      { x: -20, y: 5, vx: 0, vy: 0, r: 1, ph: 0, tw: 1, glow: false, rx: 0, ry: 0, boost: 0 },
    ];
    stepNodes(nodes, 1, 800, 600);
    expect(nodes[0]?.x).toBe(810); // < -10 → w+10
  });

  it("repel sin cursor cerca no desplaza", () => {
    const r = repel(0, 0, 9999, 9999, 1);
    expect(r).toEqual({ x: 0, y: 0, boost: 0 });
  });

  it("buildBlooms devuelve 2 specs (o vacío si aura<=0)", () => {
    expect(buildBlooms(800, 600, 0, true, 0, MODE_CLIMATE.productividad)).toHaveLength(0);
    const blooms = buildBlooms(800, 600, 0, true, 1, MODE_CLIMATE.productividad);
    expect(blooms).toHaveLength(2);
    expect(blooms[0]?.rgb).toEqual([47, 90, 166]); // #2f5aa6
    expect(blooms[0]?.alpha).toBeCloseTo(0.4); // dark
  });

  it("buildWaves devuelve 7 cintas + 5 hilos y samplea curvas finitas", () => {
    const { ribbons, threads } = buildWaves(800, 600, 1, breath(1), true, MODE_CLIMATE.bienestar);
    expect(ribbons).toHaveLength(RIBBONS);
    expect(threads).toHaveLength(THREADS);
    const r0 = ribbons[0];
    if (r0) expect(Number.isFinite(ribbonEdgeY(400, r0, -1))).toBe(true);
  });
});
