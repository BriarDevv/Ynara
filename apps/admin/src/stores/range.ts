import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Rango temporal global del panel. Vive en el chrome (topbar) y todas las
 * pantallas salvo System Health lo consumen como query param `range=`. Default
 * `7d`. Persistido con la key `ynara.admin.range` para que el operador retome
 * su ventana entre sesiones.
 */
export type RangeId = "24h" | "7d" | "30d" | "90d";

export const RANGE_IDS: readonly RangeId[] = ["24h", "7d", "30d", "90d"] as const;

type RangeState = {
  range: RangeId;
};

type RangeActions = {
  setRange: (range: RangeId) => void;
  reset: () => void;
};

const initialState: RangeState = {
  range: "7d",
};

export const useRangeStore = create<RangeState & RangeActions>()(
  persist(
    (set) => ({
      ...initialState,
      setRange: (range) => set({ range }),
      reset: () => set(initialState),
    }),
    { name: "ynara.admin.range" },
  ),
);
