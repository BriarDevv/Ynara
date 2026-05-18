import { create } from "zustand";
import { persist } from "zustand/middleware";

export type TextSize = "sm" | "md" | "lg";
export type MotionPreference = "auto" | "reduce" | "normal";

type A11yState = {
  textSize: TextSize;
  highContrast: boolean;
  /**
   * - "auto": respeta el OS-pref (prefers-reduced-motion).
   * - "reduce": fuerza off (aplica .motion-off).
   * - "normal": fuerza on (aplica .motion-on, gana sobre OS-pref).
   *
   * El modelo de clases en <html> está documentado en DESIGN.md §7 y
   * en el bloque "reduced-motion" de globals.css.
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

export const useA11yStore = create<A11yState & A11yActions>()(
  persist(
    (set) => ({
      ...initialState,
      setTextSize: (textSize) => set({ textSize }),
      setHighContrast: (highContrast) => set({ highContrast }),
      setMotion: (motion) => set({ motion }),
      reset: () => set(initialState),
    }),
    { name: "ynara.a11y" },
  ),
);

/**
 * Aplica el estado actual de a11y a las clases del <html>.
 * Llamar desde un componente client después de hidratar.
 */
export function applyA11yClasses(state: A11yState): void {
  if (typeof document === "undefined") return;
  const html = document.documentElement;

  html.classList.remove("text-size-sm", "text-size-md", "text-size-lg");
  html.classList.add(`text-size-${state.textSize}`);

  html.classList.toggle("theme-high-contrast", state.highContrast);

  html.classList.remove("motion-off", "motion-on");
  if (state.motion === "reduce") html.classList.add("motion-off");
  else if (state.motion === "normal") html.classList.add("motion-on");
}
