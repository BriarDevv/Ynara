import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ModeId } from "@/components/ui/modes";

/**
 * Modo **activo** de la app, elegible desde el sidebar (paridad con el mockup:
 * el modo re-tiñe toda la UI vía `useActiveMode` → `LivingField`/orbe/acentos).
 *
 * `mode: null` = sin override manual → `useActiveMode` deriva del onboarding
 * (primer modo de interés). En cuanto el usuario elige un modo en el sidebar,
 * queda fijado acá y persiste.
 */
type ActiveModeState = { mode: ModeId | null };
type ActiveModeActions = {
  setMode: (mode: ModeId) => void;
  reset: () => void;
};

export const useActiveModeStore = create<ActiveModeState & ActiveModeActions>()(
  persist(
    (set) => ({
      mode: null,
      setMode: (mode) => set({ mode }),
      reset: () => set({ mode: null }),
    }),
    { name: "ynara.active-mode" },
  ),
);
