import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Preferencia DISPLAY-ONLY de "mostrar el razonamiento (Pensando…)".
 *
 * El toggle SOLO muestra/oculta el colapsable de razonamiento en la UI: NO
 * controla el thinking del modelo ni manda ningún flag al backend. El backend
 * SIEMPRE emite el `reasoning` por SSE cuando el modelo razona (p. ej. modos
 * agente Qwen); el front decide si renderizarlo según `enabled`.
 *
 * Default OFF (el razonamiento es ruido para la mayoría; quien quiera verlo lo
 * prende). Web-local (no se sincroniza con mobile): clon del modelo de
 * `stores/theme.ts` / `stores/mode.ts`, persistido en localStorage.
 */
type ShowReasoningState = { enabled: boolean };
type ShowReasoningActions = {
  setEnabled: (enabled: boolean) => void;
  toggle: () => void;
  reset: () => void;
};

const initialState: ShowReasoningState = { enabled: false };

export const useShowReasoningStore = create<ShowReasoningState & ShowReasoningActions>()(
  persist(
    (set) => ({
      ...initialState,
      setEnabled: (enabled) => set({ enabled }),
      toggle: () => set((s) => ({ enabled: !s.enabled })),
      reset: () => set(initialState),
    }),
    { name: "ynara.show-reasoning" },
  ),
);
