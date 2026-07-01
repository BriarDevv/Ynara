"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { YnaraLockup } from "@/components/ui/YnaraLockup";
import { nav } from "@/content/ynara";
import { reducedMotion } from "@/lib/motion";
import { useIsDeckRoute } from "@/lib/useDeckRoute";

const HEADER_BAND = 88; // franja superior (px) donde un wipe marfil "tapa" el header

/**
 * Chrome mínimo persistente (alma infinitefield): un CTA quieto arriba-derecha y
 * la marca arriba-izquierda que APARECE A SU ENCUENTRO cuando el wordmark del
 * hero sube y se encoge (fusión hero→nav, estilo tiwis). Nada de barra SaaS.
 *
 * Conmuta a tinta OSCURA cuando un panel wipe marfil pasa bajo el header, para
 * no quedar marfil-sobre-marfil (legibilidad AA del único CTA).
 *
 * Perf: la opacidad de la marca se escribe directo al DOM (ref) bajo un único
 * cálculo por frame (rAF), sin setState por scroll. La detección de fondo marfil
 * usa IntersectionObserver contra la franja superior del header (sin
 * getBoundingClientRect en loop). En móvil (≤767px) se suma un menú accesible.
 */
export function SiteNav() {
  const isDeck = useIsDeckRoute();
  const brandRef = useRef<HTMLAnchorElement>(null);
  const [onLight, setOnLight] = useState(false);

  // --- menú mobile ---
  const [menuOpen, setMenuOpen] = useState(false);
  const menuId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const firstLinkRef = useRef<HTMLAnchorElement>(null);

  // --- marca (opacidad por scroll, escrita al DOM) + fondo marfil (IO) ---
  useEffect(() => {
    if (isDeck) return; // el nav no existe en el deck
    const el = brandRef.current;

    // Reduced-motion: la marca queda visible y quieta (sin rAF ni IO).
    if (reducedMotion()) {
      if (el) {
        el.style.opacity = "1";
        el.style.pointerEvents = "auto";
      }
      return;
    }

    // brandOp escrito directo al DOM: un cálculo por frame con rAF, no por evento.
    let raf = 0;
    const applyBrand = () => {
      raf = 0;
      const vh = window.innerHeight || 1;
      // La marca entra mientras el hero se funde (~0.4vh → 0.9vh de scroll).
      const op = Math.min(1, Math.max(0, (window.scrollY / vh - 0.4) / 0.5));
      if (el) {
        el.style.opacity = String(op);
        el.style.pointerEvents = op > 0.5 ? "auto" : "none";
      }
    };
    const onScroll = () => {
      if (raf) return; // ya hay un frame agendado → throttle a 1/frame
      raf = requestAnimationFrame(applyBrand);
    };
    applyBrand();
    window.addEventListener("scroll", onScroll, { passive: true });

    // onLight vía IntersectionObserver: ¿algún panel [data-wipe-tone="ivory"]
    // cubre la franja superior (~88px) del header? rootMargin recorta el root
    // del viewport a esa banda; se re-crea en resize para mantener el alto exacto.
    const ivoryWipes = Array.from(
      document.querySelectorAll<HTMLElement>('[data-wipe-tone="ivory"]'),
    );
    let io: IntersectionObserver | null = null;
    const visible = new Set<Element>();
    const buildObserver = () => {
      io?.disconnect();
      visible.clear();
      const vh = window.innerHeight || 1;
      io = new IntersectionObserver(
        (entries) => {
          for (const e of entries) {
            if (e.isIntersecting) visible.add(e.target);
            else visible.delete(e.target);
          }
          setOnLight(visible.size > 0);
        },
        // Banda = primeros HEADER_BAND px del viewport.
        { rootMargin: `0px 0px ${-(vh - HEADER_BAND)}px 0px`, threshold: 0 },
      );
      for (const w of ivoryWipes) io?.observe(w);
    };
    buildObserver();

    let resizeRaf = 0;
    const onResize = () => {
      applyBrand();
      if (resizeRaf) return;
      resizeRaf = requestAnimationFrame(() => {
        resizeRaf = 0;
        buildObserver();
      });
    };
    window.addEventListener("resize", onResize, { passive: true });

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      if (raf) cancelAnimationFrame(raf);
      if (resizeRaf) cancelAnimationFrame(resizeRaf);
      io?.disconnect();
    };
  }, [isDeck]);

  // Menú mobile: Escape para cerrar + foco al abrir / devolución al cerrar.
  useEffect(() => {
    if (!menuOpen) return;
    const prevFocus = document.activeElement as HTMLElement | null;
    // Foco al primer link del panel (fallback al panel).
    (firstLinkRef.current ?? panelRef.current)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setMenuOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      // Devolver el foco al disparador (el botón hamburguesa).
      (toggleRef.current ?? prevFocus)?.focus();
    };
  }, [menuOpen]);

  const reduce = typeof window !== "undefined" && reducedMotion();

  if (isDeck) return null;

  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-50">
      {/* Scrim del header, world-aware y detrás del contenido (z-index:-1):
          garantiza legibilidad de la marca + CTA sobre el campo vivo (oscuro) y
          sobre las secciones marfil (claro), y tapa el contenido que pasa por
          debajo del header fijo al scrollear (clave en mobile). */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-28 transition-[background] duration-300"
        style={{
          zIndex: -1,
          background: onLight
            ? "linear-gradient(to bottom, var(--c-ivory) 0%, color-mix(in srgb, var(--c-ivory) 60%, transparent) 50%, transparent 100%)"
            : "linear-gradient(to bottom, color-mix(in srgb, var(--c-void) 70%, transparent) 0%, transparent 100%)",
        }}
      />
      <div className="flex items-center justify-between px-[var(--gutter)] py-[clamp(1.25rem,4vh,2.25rem)]">
        <a
          ref={brandRef}
          href="#top"
          className="inline-flex transition-opacity duration-200"
          aria-label="Ynara — inicio"
          style={{ opacity: 0, pointerEvents: "none" }}
        >
          <YnaraLockup size={16} tone={onLight ? "light" : "dark"} />
        </a>

        <div className="flex items-center gap-2">
          {/* CTA: visible siempre (desktop y mobile). */}
          <Button
            href={nav.cta.href}
            size="md"
            variant="outline"
            className={
              onLight
                ? "pointer-events-auto !border-transparent !bg-navy-deep !text-ivory hover:!bg-blue"
                : "pointer-events-auto"
            }
          >
            {nav.cta.label}
          </Button>

          {/* Hamburguesa: sólo ≤767px (md:hidden). En desktop, marca + CTA. */}
          <button
            ref={toggleRef}
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"}
            aria-expanded={menuOpen}
            aria-controls={menuId}
            className="pointer-events-auto inline-flex h-11 w-11 items-center justify-center rounded-[var(--r-md)] transition-colors hover:bg-white/5 md:hidden"
          >
            {/* glifo hamburguesa / cierre — hereda color del estado onLight */}
            <span
              aria-hidden="true"
              className="relative block h-4 w-5"
              style={{ color: onLight ? "var(--c-navy)" : "var(--c-text-bright)" }}
            >
              <span
                className="absolute left-0 block h-[2px] w-5 bg-current transition-transform duration-200"
                style={{
                  top: menuOpen ? "7px" : "2px",
                  transform: menuOpen ? "rotate(45deg)" : "none",
                }}
              />
              <span
                className="absolute left-0 top-[7px] block h-[2px] w-5 bg-current transition-opacity duration-200"
                style={{ opacity: menuOpen ? 0 : 1 }}
              />
              <span
                className="absolute left-0 block h-[2px] w-5 bg-current transition-transform duration-200"
                style={{
                  top: menuOpen ? "7px" : "12px",
                  transform: menuOpen ? "rotate(-45deg)" : "none",
                }}
              />
            </span>
          </button>
        </div>
      </div>

      {/* Sheet mobile: por encima del header (z-50), sólo cuando está abierto.
          pointer-events-auto sólo al abrir; cierre con backdrop, Escape o link. */}
      {menuOpen && (
        <div className="pointer-events-auto fixed inset-0 z-[60] md:hidden" role="presentation">
          <div
            className="absolute inset-0 bg-void/70 backdrop-blur-sm"
            style={reduce ? undefined : { animation: "ynara-nav-fade 0.2s ease both" }}
            onClick={() => setMenuOpen(false)}
            aria-hidden="true"
          />
          <div
            ref={panelRef}
            id={menuId}
            role="dialog"
            aria-modal="true"
            aria-label="Menú"
            tabIndex={-1}
            className="absolute inset-x-0 top-0 border-b border-hair bg-navy-deep px-[var(--gutter)] pb-8 pt-[clamp(1.25rem,4vh,2.25rem)] shadow-[0_24px_60px_rgba(0,0,0,0.5)]"
            style={
              reduce
                ? undefined
                : { animation: "ynara-nav-slide 0.24s cubic-bezier(0.16,1,0.3,1) both" }
            }
          >
            {/* fila superior: marca + botón de cierre alineados al header */}
            <div className="mb-6 flex items-center justify-between">
              <YnaraLockup size={16} tone="dark" />
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="Cerrar menú"
                className="inline-flex h-11 w-11 items-center justify-center rounded-[var(--r-md)] text-text-bright transition-colors hover:bg-white/5"
              >
                <span aria-hidden="true" className="relative block h-4 w-5">
                  <span className="absolute left-0 top-[7px] block h-[2px] w-5 rotate-45 bg-current" />
                  <span className="absolute left-0 top-[7px] block h-[2px] w-5 -rotate-45 bg-current" />
                </span>
              </button>
            </div>

            <nav aria-label="Secciones">
              <ul className="flex flex-col">
                {nav.links.map((l, i) => (
                  <li key={l.href}>
                    <a
                      ref={i === 0 ? firstLinkRef : undefined}
                      href={l.href}
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center py-3 font-display text-xl font-medium text-text-bright transition-colors hover:text-blue-bright"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>

            <div className="mt-6">
              <Button
                href={nav.cta.href}
                size="lg"
                variant="primary"
                className="w-full"
                onClick={() => setMenuOpen(false)}
              >
                {nav.cta.label}
              </Button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
