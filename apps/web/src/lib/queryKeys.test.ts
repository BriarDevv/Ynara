import { describe, expect, it } from "vitest";
import { qk } from "./queryKeys";

describe("qk — factory de query keys", () => {
  it("genera keys jerárquicas estables", () => {
    expect(qk.sessions.all()).toEqual(["sessions"]);
    expect(qk.sessions.detail("s1")).toEqual(["sessions", "s1"]);
    expect(qk.memory.detail("semantic", "ref-1")).toEqual([
      "memory",
      "detail",
      "semantic",
      "ref-1",
    ]);
    expect(qk.memory.search("tesis")).toEqual(["memory", "search", "tesis"]);
  });

  it("comparte el prefijo ['memory'] para invalidación por prefijo", () => {
    const prefix = "memory";
    expect(qk.memory.all()[0]).toBe(prefix);
    expect(qk.memory.detail("episodic", "r")[0]).toBe(prefix);
    expect(qk.memory.search("q")[0]).toBe(prefix);
  });

  it("incluye los filtros en la key de lista (distintos filtros, distinta key)", () => {
    expect(qk.memory.all({ layer: "semantic" })).toEqual(["memory", "list", { layer: "semantic" }]);
    expect(qk.memory.all()).toEqual(["memory", "list", {}]);
  });
});
