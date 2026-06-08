"use client";

// El stylesheet de Lenis solo aporta una regla que nos interesa para el
// scroll anidado: `overscroll-behavior: contain` en `[data-lenis-prevent]`
// (lo usa el scroller del chat, MessageList) para que su scroll no encadene
// al <main>. El resto de reglas apuntan a `html.lenis` (root scroll), que no
// usamos: el shell scrollea en un contenedor interno, no en el documento.
import "lenis/dist/lenis.css";
import Lenis from "lenis";
import { usePathname } from "next/navigation";
import { type RefObject, useEffect } from "react";
import { useReducedMotion } from "./useReducedMotion";

/**
 * Smooth-scroll de Lenis sobre el contenedor de scroll del shell (DESIGN.md
 * §8.4 / §16 #7). El shell es de **viewport fijo con scroll interno** (el
 * `<main>`, no el documento), así que Lenis se monta con un `wrapper` custom.
 *
 * Reglas que se cumplen acá:
 *  - **reduced-motion** (`useReducedMotion`, reactivo al store + OS-pref): bajo
 *    reduce NO se instancia Lenis (scroll nativo). Es el mismo gate que el
 *    campo vivo (§16 #5): Lenis corre su propio `rAF` y la regla es no crearlo,
 *    no apagarlo desde CSS.
 *  - **`autoRaf: true`**: en Lenis 1.x el default es `false` — sin un driver de
 *    `rAF` (`lenis.raf(t)`), `smoothWheel` hace `preventDefault` del wheel pero
 *    nunca aplica el scroll programático → la rueda queda muerta. Con `autoRaf`
 *    Lenis maneja su propio loop y `destroy()` lo cancela.
 *  - **cleanup**: `destroy()` cancela el `rAF` (`_rafId`) y remueve los
 *    listeners; sin esto leakea por navegación (landmine (b) del plan).
 *  - **`content` explícito**: por defecto Lenis usa `document.documentElement`,
 *    inútil con wrapper custom. El contenido real es el hijo directo del
 *    `<main>`, que **cambia en cada navegación** del App Router → recreamos por
 *    `pathname` para no quedar con un `content` stale (su ResizeObserver mediría
 *    un nodo desprendido). El hijo directo es el `template` del grupo `(app)`
 *    (#8), que envuelve tanto al `loading.tsx` como a la page — así el `content`
 *    es siempre el div del template, nunca el spinner, y el supuesto se mantiene.
 *  - **teclado**: Lenis no intercepta el teclado (solo wheel/touch), así que
 *    PageUp/Down/Home/End/flechas siguen siendo nativos (landmine (d)).
 *  - **chat / formularios**: el scroll del chat NO se smoothea (landmine (a),
 *    rama "desactivarlo" del plan): su lista (MessageList) es un scroller propio
 *    con `data-lenis-prevent`, y en esa vista el `<main>` no scrollea (`h-full`),
 *    así que Lenis queda inerte. Cualquier vista del shell con formularios que
 *    no deba suavizarse usa el mismo `data-lenis-prevent`. La coordinación fina
 *    con el auto-scroll del streaming llega en #9.
 */
export function useSmoothScroll(wrapperRef: RefObject<HTMLElement | null>): void {
  const reduced = useReducedMotion();
  const pathname = usePathname();

  // `pathname` no se lee adentro pero es dep a propósito: el App Router conserva
  // el <main> entre rutas del grupo y le cambia el hijo (el content de Lenis).
  // Recrear por navegación evita un content stale (ResizeObserver sobre un nodo
  // desprendido).
  // biome-ignore lint/correctness/useExhaustiveDependencies: pathname recrea Lenis por navegación (ver arriba).
  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper || reduced) return;

    const content = wrapper.firstElementChild;
    if (!content) return;

    const lenis = new Lenis({
      wrapper,
      content,
      duration: 1.1,
      // easeOutCubic — mismo perfil suave del DS, sin rebote.
      easing: (t) => 1 - (1 - t) ** 3,
      smoothWheel: true,
      // Lenis 1.x default = false: sin esto el wheel queda preventDefault'd pero
      // sin avanzar. Con autoRaf maneja su rAF y destroy() lo cancela.
      autoRaf: true,
    });

    return () => lenis.destroy();
  }, [wrapperRef, reduced, pathname]);
}
