import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

/**
 * Store de preferencias de accesibilidad, compartido web + mobile (ADR-012).
 * Solo el estado y las acciones viven acá; cómo se APLICAN las preferencias es
 * platform-specific (web togglea clases en <html>, mobile escala texto en RN)
 * y vive en cada app.
 */
export type TextSize = "sm" | "md" | "lg";
export type MotionPreference = "auto" | "reduce" | "normal";

export type A11yState = {
  textSize: TextSize;
  highContrast: boolean;
  /**
   * - "auto": respeta el OS-pref (prefers-reduced-motion).
   * - "reduce": fuerza off.
   * - "normal": fuerza on (gana sobre OS-pref).
   */
  motion: MotionPreference;
};

type A11yActions = {
  setTextSize: (size: TextSize) => void;
  setHighContrast: (on: boolean) => void;
  setMotion: (pref: MotionPreference) => void;
  reset: () => void;
};

const initialState: A11yState = {
  textSize: "md",
  highContrast: false,
  motion: "auto",
};

/** Crea el store de a11y sobre el `storage` provisto. */
export function createA11yStore(storage: StateStorage) {
  return create<A11yState & A11yActions>()(
    persist(
      (set) => ({
        ...initialState,
        setTextSize: (textSize) => set({ textSize }),
        setHighContrast: (highContrast) => set({ highContrast }),
        setMotion: (motion) => set({ motion }),
        reset: () => set(initialState),
      }),
      { name: "ynara.a11y", storage: createJSONStorage(() => storage) },
    ),
  );
}
