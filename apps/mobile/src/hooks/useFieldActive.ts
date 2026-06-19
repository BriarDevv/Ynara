import { useFocusEffect } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { AppState } from "react-native";
import { useReducedMotion } from "react-native-reanimated";

/**
 * Indica si el fondo vivo debe ANIMARSE: false si el usuario pidió reduce-motion,
 * si la app está en background, o si la pantalla no está enfocada. Cumple las
 * reglas no negociables del DESIGN.md §2.3 (frame estático con reduce-motion,
 * cero CPU fuera de vista).
 *
 * Reduce-motion se detecta con `useReducedMotion` de reanimated (no con
 * `AccessibilityInfo.isReduceMotionEnabled`, que en Android no refleja "Quitar
 * animaciones" — verificado: devuelve false con el ajuste activo).
 */
export function useFieldActive(): boolean {
  const reduceMotion = useReducedMotion();
  const [foreground, setForeground] = useState(AppState.currentState === "active");
  const [focused, setFocused] = useState(true);

  useEffect(() => {
    const app = AppState.addEventListener("change", (s) => setForeground(s === "active"));
    return () => app.remove();
  }, []);

  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      return () => setFocused(false);
    }, []),
  );

  return !reduceMotion && foreground && focused;
}
