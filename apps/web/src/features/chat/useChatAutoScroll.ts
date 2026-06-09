"use client";

import { type RefObject, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useReducedMotion } from "@/hooks/useReducedMotion";

/** Px de tolerancia para considerar que estás "pegado al fondo". */
export const NEAR_BOTTOM_THRESHOLD = 96;

/**
 * True si el scroller está a `threshold` px o menos del fondo. Pura y sin DOM
 * a propósito: el cálculo de "¿sigue cerca del fondo?" es la lógica de riesgo
 * del auto-scroll y jsdom no tiene layout, así que se testea acá en aislamiento.
 * Un gap negativo (over-scroll elástico) también cuenta como "pegado al fondo".
 */
export function isNearBottom(
  scrollHeight: number,
  scrollTop: number,
  clientHeight: number,
  threshold = NEAR_BOTTOM_THRESHOLD,
): boolean {
  return scrollHeight - scrollTop - clientHeight <= threshold;
}

export type UseChatAutoScroll = {
  /** Mostrar el botón "ir al final" (el usuario se despegó del fondo). */
  showJumpButton: boolean;
  /** Volver al fondo (instantáneo bajo reduced-motion, smooth si no). */
  jumpToBottom: () => void;
};

/**
 * Auto-scroll inteligente del chat (§10 / PR #9).
 *
 *  - Mientras estás pegado al fondo, el contenido nuevo (mensaje nuevo o el
 *    texto que crece token a token en el stream) te mantiene pegado al fondo.
 *  - Si scrolleás para arriba, NO te arrastra: pausa el pin y expone
 *    `showJumpButton`. Tocando el botón (o volviendo al fondo a mano) se reanuda.
 *
 * Scrollea NATIVO sobre el scroller propio del chat (marcado `data-lenis-prevent`):
 * Lenis maneja el `<main>` del shell, que en la vista de chat está inerte, así
 * que no hay que pasar por `lenis.scrollTo` ni pelear con su smooth-scroll
 * (DESIGN.md §16 #7, landmine (a)). El pin por crecimiento es instantáneo a
 * propósito (un smooth por token encadenaría animaciones y daría jank); el smooth
 * se reserva para el salto deliberado del botón.
 *
 * `growthKey` cambia cuando el contenido crece; dispara la re-evaluación del pin.
 */
export function useChatAutoScroll(
  scrollerRef: RefObject<HTMLElement | null>,
  growthKey: unknown,
): UseChatAutoScroll {
  const reduced = useReducedMotion();
  // ¿El usuario sigue "pegado al fondo"? Arranca en true a propósito: una
  // conversación recién abierta baja sola al último mensaje (UX de chat). Lo
  // actualiza el listener de scroll de forma SINCRÓNICA, así el pin del
  // crecimiento (que puede correr en el mismo frame que un token) lee siempre
  // la posición real y nunca arrastra contra un scroll-up reciente.
  const stuckRef = useRef(true);
  const [showJumpButton, setShowJumpButton] = useState(false);

  const jumpToBottom = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: reduced ? "auto" : "smooth" });
    // Mover el foco al scroller (focusable vía tabIndex=-1) en vez de dejarlo
    // caer a <body> cuando el botón se desmonta: así el orden de tab sigue
    // siendo predecible (queda en la conversación, no en la raíz del documento).
    el.focus({ preventScroll: true });
    stuckRef.current = true;
    setShowJumpButton(false);
  }, [reduced, scrollerRef]);

  // Escucha el scroll del usuario. `stuckRef` se actualiza SINCRÓNICAMENTE (lo
  // lee el pin del crecimiento, que puede correr en el mismo frame que un
  // token): así nunca pinea contra un scroll-up reciente. El re-render del
  // botón sí se debouncea con rAF para no spamear setState por cada evento.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    let raf = 0;
    const onScroll = () => {
      stuckRef.current = isNearBottom(el.scrollHeight, el.scrollTop, el.clientHeight);
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        setShowJumpButton(!stuckRef.current);
      });
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      el.removeEventListener("scroll", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [scrollerRef]);

  // Al crecer el contenido: si seguís pegado al fondo, mantenelo pegado (pin
  // instantáneo); si te despegaste, ofrecé el botón en vez de arrastrarte.
  // `useLayoutEffect` (no `useEffect`): corre ANTES del paint, así el token
  // nuevo no se ve un frame en la posición vieja antes de bajar (sin jitter).
  // biome-ignore lint/correctness/useExhaustiveDependencies: `growthKey` es el disparador intencional (crecimiento del contenido); `scrollerRef` es estable.
  useLayoutEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    if (stuckRef.current) {
      el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
      setShowJumpButton(false);
    } else {
      setShowJumpButton(true);
    }
  }, [growthKey]);

  return { showJumpButton, jumpToBottom };
}
