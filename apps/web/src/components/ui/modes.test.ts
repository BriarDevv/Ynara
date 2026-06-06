import { describe, expect, it } from "vitest";
import { MODE_BY_ID, MODES, type ModeId } from "./modes";

/**
 * Contrato de tint plano (DESIGN.md §3.5): cada modo expone sus tokens
 * `--mode-*` / `--mode-*-fill` como CSS vars. La existencia de esos tokens
 * en `:root` la guarda `globals.theme.test.ts`; acá se guarda que el
 * contrato TS apunte a los nombres correctos.
 */
describe("modes — contrato de tint plano (§3.5)", () => {
  it("expone los 5 modos canónicos", () => {
    const ids: ModeId[] = ["productividad", "estudio", "bienestar", "vida", "memoria"];
    expect(MODES.map((m) => m.id)).toEqual(ids);
  });

  it("cada modo apunta a sus tokens --mode-* (tint) y --mode-*-fill (fill)", () => {
    for (const mode of MODES) {
      expect(mode.tintVar).toBe(`var(--mode-${mode.id})`);
      expect(mode.fillVar).toBe(`var(--mode-${mode.id}-fill)`);
    }
  });

  it("MODE_BY_ID indexa todos los modos por id", () => {
    for (const mode of MODES) {
      expect(MODE_BY_ID[mode.id]).toBe(mode);
    }
  });
});
