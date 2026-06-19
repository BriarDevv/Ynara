import type { Mode } from "@ynara/shared-schemas";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { asyncStorage } from "@/lib/asyncStorage";

/**
 * Modo **activo** de la app, elegible desde el selector del header de Hoy (F2).
 * Espejo mobile-local del store de web (`apps/web/src/stores/mode.ts`), sobre
 * AsyncStorage (no es secreto y persiste entre reinicios, a diferencia del
 * draft del onboarding).
 *
 * `mode: null` = sin override manual → `useActiveMode` deriva del onboarding
 * (primer modo de interés). En cuanto el usuario elige un modo, queda fijado
 * acá y persiste.
 */
type ActiveModeState = { mode: Mode | null };
type ActiveModeActions = {
  setMode: (mode: Mode) => void;
};

export const useActiveModeStore = create<ActiveModeState & ActiveModeActions>()(
  persist(
    (set) => ({
      mode: null,
      setMode: (mode) => set({ mode }),
    }),
    { name: "ynara.active-mode", storage: createJSONStorage(() => asyncStorage) },
  ),
);
