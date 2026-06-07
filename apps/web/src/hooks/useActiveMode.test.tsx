import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { ModeId } from "@/components/ui/modes";
import { useUserStore } from "@/stores/user";
import { useActiveMode } from "./useActiveMode";

describe("useActiveMode", () => {
  // El store de user persiste en localStorage (jsdom lo provee real):
  // limpiar entre casos para no dejar residuo a otros archivos de test.
  beforeEach(() => {
    useUserStore.getState().reset();
    localStorage.clear();
  });

  afterEach(() => {
    useUserStore.getState().reset();
    localStorage.clear();
  });

  it("sin modos de interés cae a productividad (default de marca)", () => {
    const { result } = renderHook(() => useActiveMode());
    expect(result.current).toBe("productividad");
  });

  it("devuelve el primer modo de interés del onboarding", () => {
    useUserStore.getState().setInterestedModes(["bienestar", "vida"]);
    const { result } = renderHook(() => useActiveMode());
    expect(result.current).toBe("bienestar");
  });

  it("saltea ids inválidos persistidos (localStorage editado / versiones viejas)", () => {
    useUserStore.getState().setInterestedModes(["jardineria", "memoria"] as ModeId[]);
    const { result } = renderHook(() => useActiveMode());
    expect(result.current).toBe("memoria");
  });

  it("reacciona cuando cambian los modos de interés", () => {
    const { result, rerender } = renderHook(() => useActiveMode());
    expect(result.current).toBe("productividad");
    useUserStore.getState().setInterestedModes(["estudio"]);
    rerender();
    expect(result.current).toBe("estudio");
  });
});
