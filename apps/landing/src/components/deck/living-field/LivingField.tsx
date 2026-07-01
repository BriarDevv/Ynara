"use client";

import {
  advanceTime,
  buildBlooms,
  buildWaves,
  DENSITY_FACTOR,
  dotColor,
  FIELD,
  type FieldDensity,
  type FieldDiamond,
  type FieldNode,
  breath as fieldBreath,
  hexToRgb,
  LINK2,
  type LivingFieldVariant,
  linkAlpha,
  MASKS,
  MODE_CLIMATE,
  nodeTwinkle,
  RIBBON_STEP,
  repel,
  ribbonEdgeY,
  seedField,
  stepDiamonds,
  stepNodes,
  THREAD_STEP,
  threadY,
  VARIANTS,
} from "./field";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/cn";
import { reducedMotion } from "@/lib/motion";
import type { Mode } from "./field";
import "./LivingField.css";

/**
 * `LivingField` — el fondo vivo del sistema (DESIGN.md §2). Dibuja en un solo
 * `<canvas>` la atmósfera de la marca: blooms de profundidad, ondas de marca,
 * campo de nodos enlazados y reactividad al cursor.
 *
 * **El modelo (geometría, animación, clima, specs de blooms/ondas) vive en
 * `@ynara/core/features/field`** — fuente única compartida con el render de
 * mobile (Skia), para que el fondo quede idéntico en las dos plataformas. Acá
 * sólo está el renderer Canvas2D + el ciclo de vida web (rAF, resize, cursor,
 * reduced-motion, pausa en background, cleanup).
 *
 * Reglas no negociables (§2.3): pausa total en `visibilitychange`, DPR capado
 * a 2, densidad acotada por área, `-z-10` + `aria-hidden` + `pointer-events-none`,
 * fade-mask que lo desvanece bajo el texto, baja opacidad por diseño,
 * reduced-motion = un frame estático.
 *
 * Montaje: SIEMPRE `absolute` dentro de un contenedor `relative isolate`.
 */

export type { FieldDensity, LivingFieldVariant } from "./field";

/**
 * Geometría persistente del campo: sobrevive a los remounts del efecto (un
 * cambio de tema/modo re-tiñe sin re-randomizar). `factor` entra al snapshot
 * porque un cambio de densidad sí exige re-generar los nodos.
 */
type FieldState = {
  w: number;
  h: number;
  factor: number;
  t: number;
  nodes: FieldNode[];
  diamonds: FieldDiamond[];
};

type Props = {
  /** Textura dominante de la pantalla (§2.2). */
  variant: LivingFieldVariant;
  /** Modo que tiñe el clima del canvas (§3.5). Default: productividad. */
  modeId?: Mode;
  /** Override puntual de densidad (default: la de la variante). */
  density?: FieldDensity;
  /** Override del fade-mask (default: el de la variante). */
  concentrate?: "top" | "full";
  className?: string;
  /** Mundo: false = claro/calmo (marca), true = oscuro. */
  dark?: boolean;
  /** Lámina activa: pausa el rAF cuando NO lo está (perf con varios campos). */
  active?: boolean;
};

export function LivingField({
  variant,
  modeId = "productividad",
  density,
  concentrate,
  className,
  dark = false,
  active = true,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<FieldState>({ w: 0, h: 0, factor: 0, t: 0, nodes: [], diamonds: [] });
  const reduced = reducedMotion();
  const cfg = VARIANTS[variant];
  const dens = density ?? cfg.density;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const host = canvas.parentElement;
    if (!host) return;

    // Geometría sembrada desde el snapshot del mount anterior: un remount por
    // cambio de tema/modo no rebaraja nada.
    let { w, h, t, nodes, diamonds } = stateRef.current;
    let dpr = 1;
    let raf = 0;
    let running = true;
    let last = 0;

    // Cursor (px relativos al host) + factor de presencia que entra/sale suave.
    let pcx = -9999;
    let pcy = -9999;
    let tpcx = -9999;
    let tpcy = -9999;
    let pAlpha = 0;
    let pActive = false;

    const factor = DENSITY_FACTOR[dens];
    const climate = MODE_CLIMATE[modeId];
    const [R, G, B] = hexToRgb(climate.a);
    const rgba = (a: number) => `rgba(${R},${G},${B},${a})`;
    const rgbaOf = (rgb: readonly [number, number, number], a: number) =>
      `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a})`;
    const [DR, DG, DB] = dotColor(dark);
    const dotRgba = (a: number) => `rgba(${DR},${DG},${DB},${a})`;

    function init() {
      const g = seedField(w, h, factor, cfg.particles);
      nodes = g.nodes;
      diamonds = g.diamonds;
    }

    function resize() {
      if (!canvas || !ctx || !host) return;
      const r = host.getBoundingClientRect();
      const nw = Math.max(1, r.width);
      const nh = Math.max(1, r.height);
      // Guard: sin cambio real de tamaño/densidad no se re-randomiza el campo
      // (el ResizeObserver y los remounts por tema/modo disparan con el mismo
      // tamaño y la geometría sembrada).
      if (nw === w && nh === h && stateRef.current.factor === factor) return;
      w = nw;
      h = nh;
      // DPR capado a 2 (§2.3).
      dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      init();
      if (reduced) draw(false, 1);
    }

    /** Dibuja un frame. `dt` viene en "frames de 60fps" (1 = 16.67ms). */
    function draw(animated: boolean, dt: number) {
      if (!ctx) return;
      t = advanceTime(t, dt);
      const breath = fieldBreath(t);
      // Seguimiento suave del cursor.
      if (cfg.pointer) {
        pAlpha += ((pActive ? 1 : 0) - pAlpha) * Math.min(1, 0.05 * dt);
        if (pcx < -9000) {
          pcx = tpcx;
          pcy = tpcy;
        } else {
          const ease = Math.min(1, 0.16 * dt);
          pcx += (tpcx - pcx) * ease;
          pcy += (tpcy - pcy) * ease;
        }
      }
      const pOn = cfg.pointer && pAlpha > 0.002;

      ctx.clearRect(0, 0, w, h);

      // ── Blooms de profundidad (gradientes ambientales, en el canvas — §3.4). ──
      for (const bl of buildBlooms(w, h, t, dark, cfg.aura, climate)) {
        const g = ctx.createRadialGradient(bl.cx, bl.cy, 0, bl.cx, bl.cy, bl.r);
        g.addColorStop(0, rgbaOf(bl.rgb, bl.alpha));
        g.addColorStop(1, rgbaOf(bl.rgb, 0));
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }

      // ── Ondas de marca: cintas + hilos (la estética del poster, §2.1). ──
      if (cfg.waves) {
        const { ribbons, threads } = buildWaves(w, h, t, breath, dark, climate);
        for (const rb of ribbons) {
          ctx.beginPath();
          for (let x = 0; x <= w; x += RIBBON_STEP) {
            const y = ribbonEdgeY(x, rb, -1);
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          for (let x = w; x >= 0; x -= RIBBON_STEP) ctx.lineTo(x, ribbonEdgeY(x, rb, 1));
          ctx.closePath();
          const g = ctx.createLinearGradient(0, 0, w, 0);
          g.addColorStop(0, rgbaOf(rb.rgb, 0));
          g.addColorStop(0.3, rgbaOf(rb.rgb, rb.aEnd * 0.55));
          g.addColorStop(1, rgbaOf(rb.rgb, rb.aEnd));
          ctx.fillStyle = g;
          ctx.fill();
        }
        for (const th of threads) {
          ctx.beginPath();
          for (let x = 0; x <= w; x += THREAD_STEP) {
            const y = threadY(x, th);
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          const gs = ctx.createLinearGradient(0, 0, w, 0);
          gs.addColorStop(0, rgbaOf(th.rgb, 0));
          gs.addColorStop(0.5, rgbaOf(th.rgb, th.aEnd));
          gs.addColorStop(1, rgbaOf(th.rgb, th.aEnd * 0.85));
          ctx.strokeStyle = gs;
          ctx.lineWidth = 1.1;
          ctx.stroke();
        }
      }

      // Halo de presencia: brillo suave que sigue al cursor (§2.1).
      if (pOn) {
        const HR = FIELD.PRADIUS * 1.35;
        const gr = ctx.createRadialGradient(pcx, pcy, 0, pcx, pcy, HR);
        gr.addColorStop(0, rgba((dark ? 0.075 : 0.055) * pAlpha));
        gr.addColorStop(1, rgba(0));
        ctx.fillStyle = gr;
        ctx.fillRect(pcx - HR, pcy - HR, HR * 2, HR * 2);
      }

      // ── Campo de nodos: hilos + nodos + diamantes (§1). ──
      if (cfg.particles) {
        // Avance de estado (deriva + fase) por frame; con reduce no corre.
        if (animated) {
          stepNodes(nodes, dt, w, h);
          stepDiamonds(diamonds, dt);
        }
        const N = nodes.length;

        // Posición de render = deriva + repulsión suave del cursor (spring-back).
        for (let i = 0; i < N; i++) {
          const n = nodes[i] as FieldNode;
          if (pOn) {
            const rr = repel(n.x, n.y, pcx, pcy, pAlpha);
            n.rx = rr.x;
            n.ry = rr.y;
            n.boost = rr.boost;
          } else {
            n.rx = n.x;
            n.ry = n.y;
            n.boost = 0;
          }
        }

        // Hilos (se iluminan cerca del cursor).
        for (let i = 0; i < N; i++) {
          const a = nodes[i] as FieldNode;
          for (let j = i + 1; j < N; j++) {
            const b = nodes[j] as FieldNode;
            const dx = a.rx - b.rx;
            const dy = a.ry - b.ry;
            const d2 = dx * dx + dy * dy;
            if (d2 < LINK2) {
              ctx.strokeStyle = rgba(linkAlpha(d2, cfg.link, breath, a.boost + b.boost));
              ctx.lineWidth = 1;
              ctx.beginPath();
              ctx.moveTo(a.rx, a.ry);
              ctx.lineTo(b.rx, b.ry);
              ctx.stroke();
            }
          }
        }

        // Nodos (puntos de luz que titilan y derivan).
        for (let i = 0; i < N; i++) {
          const n = nodes[i] as FieldNode;
          const tw = nodeTwinkle(n.ph);
          if (n.glow || n.boost > 0.08) {
            ctx.fillStyle = rgba((0.1 + n.boost * 0.42) * tw * breath + n.boost * 0.12);
            ctx.beginPath();
            ctx.arc(n.rx, n.ry, n.r * (4.5 + n.boost * 5), 0, 6.2832);
            ctx.fill();
          }
          ctx.fillStyle = dotRgba((0.42 + 0.5 * tw) * (0.72 + 0.28 * breath) + n.boost * 0.55);
          ctx.beginPath();
          ctx.arc(n.rx, n.ry, n.r * (1 + n.boost * 0.9), 0, 6.2832);
          ctx.fill();
        }

        // Diamantes (acento de marca).
        for (const d of diamonds) {
          const rr = pOn ? repel(d.x, d.y, pcx, pcy, pAlpha, 1.3) : { x: d.x, y: d.y, boost: 0 };
          const a = (0.32 + 0.32 * Math.sin(d.ph)) * breath;
          ctx.save();
          ctx.translate(rr.x, rr.y);
          ctx.rotate(Math.PI / 4);
          if (d.filled) {
            ctx.fillStyle = rgba(a);
            ctx.fillRect(-d.s / 2, -d.s / 2, d.s, d.s);
          } else {
            ctx.strokeStyle = rgba(a + 0.1);
            ctx.lineWidth = 1.3;
            ctx.strokeRect(-d.s / 2, -d.s / 2, d.s, d.s);
          }
          ctx.restore();
        }
      }
    }

    const FRAME = 1000 / 60;

    function loop(ts: number) {
      if (!running) return;
      const dt = last === 0 ? 1 : Math.min(3, (ts - last) / FRAME);
      last = ts;
      draw(true, dt);
      raf = requestAnimationFrame(loop);
    }

    resize();
    if (reduced || !active) {
      draw(false, 1);
    } else {
      raf = requestAnimationFrame(loop);
    }

    // Pausa total cuando la pestaña no está visible: cero CPU en background.
    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(raf);
      } else if (!reduced && active && !running) {
        running = true;
        last = 0;
        raf = requestAnimationFrame(loop);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    const onResize = () => resize();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onResize) : null;
    if (ro) ro.observe(host);
    else window.addEventListener("resize", onResize);

    // Cursor: se escucha en window (el host es pointer-events-none).
    let onMove: ((e: PointerEvent) => void) | null = null;
    let onLeave: (() => void) | null = null;
    if (cfg.pointer && !reduced) {
      onMove = (e) => {
        // §2.1: en touch/mobile no hay cursor — queda el campo en deriva.
        if (e.pointerType === "touch") return;
        if (!host) return;
        const r = host.getBoundingClientRect();
        tpcx = e.clientX - r.left;
        tpcy = e.clientY - r.top;
        pActive = true;
      };
      onLeave = () => {
        pActive = false;
      };
      window.addEventListener("pointermove", onMove, { passive: true });
      window.addEventListener("pointerdown", onMove, { passive: true });
      window.addEventListener("blur", onLeave);
      document.addEventListener("mouseleave", onLeave);
    }

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      // Snapshot para el próximo mount: mismas posiciones y tiempo → un cambio
      // de color re-tiñe con cero salto visual.
      stateRef.current = { w, h, factor, t, nodes, diamonds };
      if (ro) ro.disconnect();
      else window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      if (onMove) {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerdown", onMove);
      }
      if (onLeave) {
        window.removeEventListener("blur", onLeave);
        document.removeEventListener("mouseleave", onLeave);
      }
    };
  }, [cfg, modeId, dens, dark, reduced, active]);

  const mask = MASKS[concentrate ?? cfg.concentrate];

  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 select-none overflow-hidden",
        className,
      )}
    >
      {/* Capa canvas con fade-mask: baja opacidad por diseño — es atmósfera. */}
      <div
        className="field-atmosphere absolute inset-0"
        style={{
          opacity: dark ? 0.52 : 0.5,
          maskImage: mask,
          WebkitMaskImage: mask,
        }}
      >
        <canvas ref={canvasRef} className="absolute inset-0 block h-full w-full" />
      </div>
      {/* Grano: materia física / papel (§3.6). Capa CSS estática. */}
      {cfg.grain > 0 && (
        <div
          className="field-grain absolute inset-0"
          style={{ opacity: cfg.grain * (dark ? 1 : 0.82) }}
        />
      )}
    </div>
  );
}
