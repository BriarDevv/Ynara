"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { YnaraLockup } from "@/components/ui/YnaraLockup";
import { DECK_SLIDES, TOTAL_SLIDES } from "@/content/deck";
import { gsap, reducedMotion } from "@/lib/motion";
import { DeckContext } from "./deck-context";
import "./Deck.css";

// El campo es client-only (WebGL). En el deck lo conducimos a mano por lámina.
const CascadeField = dynamic(() => import("@/components/field/CascadeField"), { ssr: false });

const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);

/**
 * DECK — presentación institucional a pantalla completa, navegada por TECLADO
 * (no por scroll): ←/→ · espacio · Re/Av Pág · Inicio/Fin, swipe táctil y click.
 * Una sola lámina activa por vez (crossfade); cada una reproduce su entrada al
 * activarse. Un único campo WebGL persistente detrás, conducido por la fase de
 * la lámina activa (caos↔calma). Respeta prefers-reduced-motion.
 */
export function Deck({ children }: { children: React.ReactNode }) {
  const [{ active, dir }, setState] = useState({ active: 0, dir: 1 });

  const go = useCallback(
    (i: number) =>
      setState((s) => {
        const n = clamp(i, 0, TOTAL_SLIDES - 1);
        return n === s.active ? s : { active: n, dir: n > s.active ? 1 : -1 };
      }),
    [],
  );
  const next = useCallback(
    () => setState((s) => ({ active: Math.min(s.active + 1, TOTAL_SLIDES - 1), dir: 1 })),
    [],
  );
  const prev = useCallback(
    () => setState((s) => ({ active: Math.max(s.active - 1, 0), dir: -1 })),
    [],
  );

  const ctx = useMemo(
    () => ({ active, total: TOTAL_SLIDES, dir, go, next, prev }),
    [active, dir, go, next, prev],
  );

  // ── Teclado (global; no necesita foco) ──────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      switch (e.key) {
        case "ArrowRight":
        case "PageDown":
        case " ":
        case "Spacebar":
        case "Enter":
          e.preventDefault();
          next();
          break;
        case "ArrowLeft":
        case "PageUp":
          e.preventDefault();
          prev();
          break;
        case "Home":
          e.preventDefault();
          go(0);
          break;
        case "End":
          e.preventDefault();
          go(TOTAL_SLIDES - 1);
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, go]);

  // ── Campo: conducir la fase a la de la lámina activa (transición suave) ──
  const fieldProxy = useRef({ p: DECK_SLIDES[0].field });
  // Set inicial en cuanto CascadeField exponga el driver global.
  useEffect(() => {
    let raf = 0;
    let tries = 0;
    const tick = () => {
      if (window.__setFieldProgress) {
        window.__setFieldProgress(DECK_SLIDES[0].field);
        return;
      }
      if (tries++ < 180) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  useEffect(() => {
    const target = DECK_SLIDES[active]?.field ?? 0.3;
    if (reducedMotion()) {
      window.__setFieldProgress?.(target);
      return;
    }
    const tw = gsap.to(fieldProxy.current, {
      p: target,
      duration: 1.2,
      ease: "power2.inOut",
      onUpdate: () => window.__setFieldProgress?.(fieldProxy.current.p),
    });
    return () => {
      tw.kill();
    };
  }, [active]);

  // ── Táctil (swipe) ──────────────────────────────────────────────────────
  const touch = useRef<{ x: number; y: number } | null>(null);
  const onTouchStart = (e: React.TouchEvent) => {
    const t = e.changedTouches[0];
    touch.current = { x: t.clientX, y: t.clientY };
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    const s = touch.current;
    if (!s) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - s.x;
    const dy = t.clientY - s.y;
    if (Math.abs(dx) > 44 && Math.abs(dx) > Math.abs(dy)) {
      if (dx < 0) next();
      else prev();
    }
    touch.current = null;
  };

  // ── Click en el fondo → avanzar (los enlaces/botones no avanzan) ─────────
  const onStageClick = (e: React.MouseEvent) => {
    const t = e.target as HTMLElement | null;
    if (t?.closest("a, button, [data-no-advance]")) return;
    next();
  };

  const world = DECK_SLIDES[active].world;
  const meta = DECK_SLIDES[active];

  return (
    <DeckContext.Provider value={ctx}>
      <div className="deck" data-world={world}>
        {/* Campo persistente (una sola instancia WebGL), conducido por lámina. */}
        <div className="deck-field" aria-hidden>
          <CascadeField bare />
          <div className="deck-field__scrim" />
          <div className="deck-field__vignette" />
          <div className="grain deck-field__grain" />
        </div>

        {/* biome-ignore lint/a11y/useKeyWithClickEvents: navegación por teclado global (window) + flechas */}
        <section
          className="deck-stage"
          aria-label="Presentación de Ynara"
          onClick={onStageClick}
          onTouchStart={onTouchStart}
          onTouchEnd={onTouchEnd}
        >
          {children}
        </section>

        {/* Anuncio para lectores de pantalla al cambiar de lámina. */}
        <p className="sr-only" aria-live="polite">
          {`Diapositiva ${meta.id} de ${TOTAL_SLIDES}: ${meta.section}`}
        </p>

        {/* Chrome de navegación, discreto, adaptado al mundo de la lámina. */}
        <div className={`deck-chrome is-${world}`} data-no-advance>
          <div className="deck-chrome__brand">
            <YnaraLockup size={16} tone={world === "ivory" ? "light" : "dark"} />
          </div>
          <div className="deck-chrome__nav">
            <button
              type="button"
              className="deck-arrow"
              onClick={prev}
              disabled={active === 0}
              aria-label="Diapositiva anterior"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none">
                <path
                  d="M15 5l-7 7 7 7"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            <span className="deck-counter">
              <span className="deck-counter__cur">{String(meta.id).padStart(2, "0")}</span>
              <span className="deck-counter__sep"> / </span>
              <span className="deck-counter__total">{String(TOTAL_SLIDES).padStart(2, "0")}</span>
              <span className="deck-counter__section">{meta.section}</span>
            </span>
            <button
              type="button"
              className="deck-arrow"
              onClick={next}
              disabled={active === TOTAL_SLIDES - 1}
              aria-label="Diapositiva siguiente"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none">
                <path
                  d="M9 5l7 7-7 7"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
          <div className="deck-progress" aria-hidden>
            <span
              className="deck-progress__bar"
              style={{ width: `${((active + 1) / TOTAL_SLIDES) * 100}%` }}
            />
          </div>
        </div>
      </div>
    </DeckContext.Provider>
  );
}
