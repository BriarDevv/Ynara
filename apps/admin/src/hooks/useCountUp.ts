"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "./useReducedMotion";

/**
 * Cuenta 0 → `target` con `requestAnimationFrame` (~600ms, easing suave) para
 * los números grandes de los charts (centro del donut, totales, KPIs). Se
 * **neutraliza** bajo reduced-motion / `html.motion-off`: en ese caso devuelve
 * el valor final de una sin animar (regla de a11y del DS: el override manual y
 * el OS-pref ganan, ver `useReducedMotion`).
 *
 * Solo anima al montar (primer load del dato); si `target` cambia luego, salta
 * al nuevo valor sin re-animar para no marear en cada refetch del rango.
 */
export function useCountUp(target: number, durationMs = 600): number {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(reduced ? target : 0);
  const started = useRef(false);

  useEffect(() => {
    if (reduced) {
      setValue(target);
      return;
    }
    if (started.current) {
      setValue(target);
      return;
    }
    started.current = true;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      // ease-out cúbico: arranca rápido, frena al final (sensación de "asentar").
      const eased = 1 - (1 - t) ** 3;
      setValue(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else setValue(target);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs, reduced]);

  return value;
}
