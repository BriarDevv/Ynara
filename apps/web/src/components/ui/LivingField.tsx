"use client";

import { useEffect, useRef } from "react";
import { MODE_CLIMATE, type ModeId } from "@/components/ui/modes";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { cn } from "@/lib/cn";
import { useThemeStore } from "@/stores/theme";

/**
 * `LivingField` — el fondo vivo del sistema v4 (DESIGN.md §2). Dibuja en un
 * solo `<canvas>` detrás del contenido la atmósfera de la marca: blooms de
 * profundidad, ondas de marca, campo de nodos enlazados y reactividad al
 * cursor. Port de `canvas-field.jsx` + `CalmBg` del prototipo (§15), con
 * tres endurecimientos sobre el original:
 *
 * - **Reduced-motion en JS** (§2.3): usa `useReducedMotion` (override del
 *   store de a11y + OS-pref, reactivo en runtime), no el `matchMedia` crudo.
 *   Con reduce dibuja un único frame estático — el CSS no puede frenar un
 *   `requestAnimationFrame`.
 * - **Velocidad normalizada por delta-time**: el prototipo avanzaba un paso
 *   fijo por frame (a 120Hz corría al doble); acá todo escala por `dt`.
 * - **Cleanup completo**: cancela el rAF y remueve todos los listeners de
 *   window/document al desmontar (primer loop de rAF del repo — si leakea,
 *   leakea por navegación). Hay test de unmount.
 *
 * Reglas no negociables que implementa (§2.3): pausa total en
 * `visibilitychange`, DPR capado a 2, densidad acotada por área, `-z-10` +
 * `aria-hidden` + `pointer-events-none`, fade-mask que lo desvanece bajo el
 * texto, baja opacidad por diseño.
 *
 * Montaje: SIEMPRE `absolute` dentro de un contenedor `relative isolate`
 * (nunca `fixed`: el `AppShell` crea `isolate` y el `-z-10` quedaría
 * atrapado). Cada pantalla destaca UNA variante (§2.2).
 */

export type LivingFieldVariant = "aurora" | "constellation" | "network" | "paper" | "depth";

export type FieldDensity = "sutil" | "media" | "intensa";

type VariantConfig = {
  /** Ondas de marca (cintas + hilos, estética del manual). */
  waves: boolean;
  /** Campo de nodos (estrellas + hilos + diamantes). */
  particles: boolean;
  /** Reactividad al cursor (halo de presencia + repulsión suave). */
  pointer: boolean;
  density: FieldDensity;
  /** Énfasis de los hilos entre nodos (red). */
  link: number;
  /** Opacidad del grano (capa CSS estática, §3.6). */
  grain: number;
  /** Fuerza de los blooms de profundidad. */
  aura: number;
  concentrate: "top" | "full";
};

/** Cada pantalla destaca UNA textura del repertorio (DESIGN.md §2.2). */
const VARIANTS: Record<LivingFieldVariant, VariantConfig> = {
  // Hoy: ondas que fluyen + atmósfera.
  aurora: {
    waves: true,
    particles: true,
    pointer: true,
    density: "sutil",
    link: 0.8,
    grain: 0.42,
    aura: 1,
    concentrate: "top",
  },
  // Hablar / onboarding / paywall: campo de nodos denso (estrellas).
  constellation: {
    waves: false,
    particles: true,
    pointer: true,
    density: "intensa",
    link: 0.5,
    grain: 0.3,
    aura: 0.85,
    concentrate: "full",
  },
  // Memoria: red de nodos con hilos marcados.
  network: {
    waves: false,
    particles: true,
    pointer: true,
    density: "media",
    link: 2.4,
    grain: 0.28,
    aura: 0.9,
    concentrate: "full",
  },
  // Agenda (pendiente): grano — limpio, casi quieto, sin cursor.
  paper: {
    waves: false,
    particles: true,
    pointer: false,
    density: "sutil",
    link: 0.25,
    grain: 0.85,
    aura: 0.5,
    concentrate: "top",
  },
  // Tu/perfil (pendiente): profundidad pura (blooms, sin partículas).
  depth: {
    waves: false,
    particles: false,
    pointer: false,
    density: "sutil",
    link: 1,
    grain: 0.5,
    aura: 1.6,
    concentrate: "full",
  },
};

/** Fade-mask: concentra el campo arriba (zona de presencia) y lo desvanece
 *  bajo el texto — el contraste se mide contra el plano, no contra la
 *  atmósfera (§3.8). */
const MASKS = {
  top: "linear-gradient(180deg, #000 0%, #000 34%, rgba(0, 0, 0, 0.5) 68%, transparent 98%)",
  full: "radial-gradient(125% 95% at 50% 0%, #000 0%, #000 30%, transparent 86%)",
} as const;

const DENSITY_FACTOR: Record<FieldDensity, number> = { sutil: 0.55, media: 1, intensa: 1.7 };

function hexToRgb(hex: string): readonly [number, number, number] {
  const h = hex.replace("#", "");
  return [
    Number.parseInt(h.slice(0, 2), 16),
    Number.parseInt(h.slice(2, 4), 16),
    Number.parseInt(h.slice(4, 6), 16),
  ];
}

type FieldNode = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  ph: number;
  tw: number;
  glow: boolean;
  /** Posición de render (deriva + repulsión del cursor), por frame. */
  rx: number;
  ry: number;
  boost: number;
};

type FieldDiamond = {
  x: number;
  y: number;
  s: number;
  ph: number;
  filled: boolean;
};

/**
 * Geometría persistente del campo: sobrevive a los remounts del efecto.
 * `dark` y `modeId` solo afectan colores — si re-corren el efecto, el guard
 * de resize() encuentra la geometría intacta y NO re-randomiza: el campo se
 * re-tiñe sin saltar. `factor` entra al snapshot porque un cambio de
 * densidad sí exige re-generar los nodos.
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
  modeId?: ModeId;
  /** Override puntual de densidad (default: la de la variante). */
  density?: FieldDensity;
  /** Override del fade-mask (default: el de la variante). */
  concentrate?: "top" | "full";
  className?: string;
};

export function LivingField({
  variant,
  modeId = "productividad",
  density,
  concentrate,
  className,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<FieldState>({ w: 0, h: 0, factor: 0, t: 0, nodes: [], diamonds: [] });
  const reduced = useReducedMotion();
  const dark = useThemeStore((s) => s.theme === "dark");
  const cfg = VARIANTS[variant];
  const dens = density ?? cfg.density;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    // jsdom / canvas sin soporte: el fondo es decorativo, no pasa nada.
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const host = canvas.parentElement;
    if (!host) return;

    // Geometría sembrada desde el snapshot del mount anterior (ver
    // FieldState): un remount por cambio de tema/modo no rebaraja nada.
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
    const [R2, G2, B2] = hexToRgb(climate.b);
    const rgba = (a: number) => `rgba(${R},${G},${B},${a})`;
    // Punto de luz: azul tinta en claro, lavanda pálida en Noche.
    const dot = dark ? ([200, 212, 245] as const) : ([70, 96, 166] as const);
    const dotRgba = (a: number) => `rgba(${dot[0]},${dot[1]},${dot[2]},${a})`;

    const rand = (a: number, b: number) => a + Math.random() * (b - a);

    function init() {
      // Densidad acotada por área (§2.3): cap duro de 130 nodos. Los hilos
      // son O(N²), pero a N=130 son ~8.4k pares/frame — y en mobile el área
      // chica baja el count solo.
      const count = Math.max(10, Math.min(130, Math.round(((w * h) / 12500) * factor)));
      nodes = [];
      for (let i = 0; i < count; i++) {
        nodes.push({
          x: Math.random() * w,
          y: Math.random() * h,
          vx: rand(-0.09, 0.09),
          vy: rand(-0.09, 0.09),
          r: rand(0.8, 2.4),
          ph: Math.random() * Math.PI * 2,
          tw: rand(0.6, 1.4),
          glow: Math.random() > 0.82,
          rx: 0,
          ry: 0,
          boost: 0,
        });
      }
      const dc = Math.max(2, Math.round(count * 0.12));
      diamonds = [];
      for (let i = 0; i < dc; i++) {
        diamonds.push({
          x: Math.random() * w,
          y: Math.random() * h,
          s: rand(4, 8),
          ph: Math.random() * Math.PI * 2,
          filled: Math.random() > 0.5,
        });
      }
    }

    function resize() {
      if (!canvas || !ctx || !host) return;
      const r = host.getBoundingClientRect();
      const nw = Math.max(1, r.width);
      const nh = Math.max(1, r.height);
      // El ResizeObserver dispara un callback inicial (y reflows de fuentes
      // disparan más) con el MISMO tamaño, y los remounts del efecto por
      // cambio de tema/modo llegan acá con la geometría sembrada: sin este
      // guard, cada uno re-randomizaría el campo — y bajo reduce,
      // re-dibujaría el frame "estático" una y otra vez. Solo un cambio
      // real de tamaño o de densidad re-genera.
      if (nw === w && nh === h && stateRef.current.factor === factor) return;
      w = nw;
      h = nh;
      // DPR capado a 2 (§2.3): a 3x el costo de fill sube sin ganancia visible.
      dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      init();
      // Con reduce el loop no corre: re-dibujar el frame estático a mano.
      if (reduced) draw(false, 1);
    }

    const LINK = 108; // distancia de enlace entre nodos
    const LINK2 = LINK * LINK;
    const PRADIUS = 175; // radio de la fuerza del cursor
    const PR2 = PRADIUS * PRADIUS;
    const PUSH = 22; // intensidad de la repulsión

    /** Dibuja un frame. `dt` viene en "frames de 60fps" (1 = 16.67ms). */
    function draw(animated: boolean, dt: number) {
      if (!ctx) return;
      t += 0.0045 * dt;
      const breath = 0.62 + 0.38 * Math.sin(t * 1.3); // respiración global
      // Seguimiento suave del cursor: el campo "te siente" cerca del puntero.
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

      // ── Profundidad: blooms de color que derivan lento. Acá viven los
      //    gradientes ambientales — en el canvas, no en la UI (§3.4). ──
      if (cfg.aura > 0) {
        const dx = Math.sin(t * 0.3) * w * 0.03;
        const dy = Math.cos(t * 0.26) * h * 0.03;
        const rad = Math.max(w, h);
        const b1 = (dark ? 0.4 : 0.28) * cfg.aura;
        const g1 = ctx.createRadialGradient(
          w * 0.26 + dx,
          h * 0.02 + dy,
          0,
          w * 0.26 + dx,
          h * 0.02 + dy,
          rad * 0.62,
        );
        g1.addColorStop(0, `rgba(${R},${G},${B},${b1})`);
        g1.addColorStop(1, `rgba(${R},${G},${B},0)`);
        ctx.fillStyle = g1;
        ctx.fillRect(0, 0, w, h);
        const b2 = (dark ? 0.32 : 0.22) * cfg.aura;
        const g2 = ctx.createRadialGradient(
          w * 0.82 - dx,
          -h * 0.02 + dy,
          0,
          w * 0.82 - dx,
          -h * 0.02 + dy,
          rad * 0.55,
        );
        g2.addColorStop(0, `rgba(${R2},${G2},${B2},${b2})`);
        g2.addColorStop(1, `rgba(${R2},${G2},${B2},0)`);
        ctx.fillStyle = g2;
        ctx.fillRect(0, 0, w, h);
      }

      // ── Ondas de marca: cintas horizontales con gradiente izq→der + hilos
      //    finos que las siguen (la estética literal del poster, §2.1). ──
      if (cfg.waves) {
        // Acento, clima y tres stops oficiales (§3.4): lavanda, violeta,
        // celeste — referenciados vía MODE_CLIMATE para quedar bajo el guard.
        const cols: ReadonlyArray<readonly [number, number, number]> = [
          [R, G, B],
          [R2, G2, B2],
          hexToRgb(MODE_CLIMATE.memoria.b), // lavanda
          hexToRgb(MODE_CLIMATE.bienestar.a), // violeta
          hexToRgb(MODE_CLIMATE.productividad.b), // celeste
        ];
        const RIBBONS = 7;
        for (let k = 0; k < RIBBONS; k++) {
          const cy = h * (0.1 + k * 0.075);
          const amp = h * (0.034 + k * 0.012);
          const thick = h * (0.075 + (k % 3) * 0.022);
          const wl = w * (0.9 + (k % 3) * 0.34);
          const ph = t * (0.32 + k * 0.13);
          const col = cols[k % cols.length] as readonly [number, number, number];
          const aEnd =
            (dark ? 0.34 : 0.25) *
            (0.84 + 0.16 * Math.sin(t * 0.4 + k * 0.9)) *
            (0.8 + 0.2 * breath);
          ctx.beginPath();
          for (let x = 0; x <= w; x += 12) {
            const u = (x / wl) * 6.2832;
            const y =
              cy - thick / 2 + Math.sin(u + ph) * amp + Math.sin(u * 0.5 - ph * 1.2) * amp * 0.32;
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          for (let x = w; x >= 0; x -= 12) {
            const u = (x / wl) * 6.2832;
            const y =
              cy + thick / 2 + Math.sin(u + ph) * amp + Math.sin(u * 0.5 - ph * 1.2) * amp * 0.32;
            ctx.lineTo(x, y);
          }
          ctx.closePath();
          const g = ctx.createLinearGradient(0, 0, w, 0);
          g.addColorStop(0, `rgba(${col[0]},${col[1]},${col[2]},0)`);
          g.addColorStop(0.3, `rgba(${col[0]},${col[1]},${col[2]},${aEnd * 0.55})`);
          g.addColorStop(1, `rgba(${col[0]},${col[1]},${col[2]},${aEnd})`);
          ctx.fillStyle = g;
          ctx.fill();
        }
        // Hilos que siguen las cintas (más finos, marcados hacia la derecha).
        for (let k = 0; k < 5; k++) {
          const cy = h * (0.12 + k * 0.1);
          const amp = h * (0.045 + k * 0.014);
          const wl = w * (0.96 + (k % 2) * 0.28);
          const ph = t * (0.28 + k * 0.12) + k * 1.1;
          const col = cols[(k + 1) % cols.length] as readonly [number, number, number];
          const aEnd = (dark ? 0.42 : 0.32) * (0.8 + 0.2 * breath);
          ctx.beginPath();
          for (let x = 0; x <= w; x += 10) {
            const u = (x / wl) * 6.2832;
            const y = cy + Math.sin(u + ph) * amp + Math.sin(u * 0.5 - ph) * amp * 0.3;
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          const gs = ctx.createLinearGradient(0, 0, w, 0);
          gs.addColorStop(0, `rgba(${col[0]},${col[1]},${col[2]},0)`);
          gs.addColorStop(0.5, `rgba(${col[0]},${col[1]},${col[2]},${aEnd})`);
          gs.addColorStop(1, `rgba(${col[0]},${col[1]},${col[2]},${aEnd * 0.85})`);
          ctx.strokeStyle = gs;
          ctx.lineWidth = 1.1;
          ctx.stroke();
        }
      }

      // Halo de presencia: brillo suave que sigue al cursor (§2.1).
      if (pOn) {
        const HR = PRADIUS * 1.35;
        const gr = ctx.createRadialGradient(pcx, pcy, 0, pcx, pcy, HR);
        gr.addColorStop(0, rgba((dark ? 0.075 : 0.055) * pAlpha));
        gr.addColorStop(1, rgba(0));
        ctx.fillStyle = gr;
        ctx.fillRect(pcx - HR, pcy - HR, HR * 2, HR * 2);
      }

      // ── Campo de nodos: hilos + nodos + diamantes (Memoria/Conexión, §1). ──
      if (cfg.particles) {
        const N = nodes.length;

        // Posición de render = deriva + repulsión suave del cursor. El offset
        // se calcula por frame, así vuelve solo (spring-back) al alejarse.
        for (let i = 0; i < N; i++) {
          const n = nodes[i] as FieldNode;
          let X = n.x;
          let Y = n.y;
          let boost = 0;
          if (pOn) {
            const dx = X - pcx;
            const dy = Y - pcy;
            const d2 = dx * dx + dy * dy;
            if (d2 < PR2) {
              const d = Math.sqrt(d2) || 0.001;
              const f = 1 - d / PRADIUS; // 0 en el borde, 1 en el centro
              const push = f * f * PUSH * pAlpha;
              X += (dx / d) * push;
              Y += (dy / d) * push;
              boost = f * pAlpha;
            }
          }
          n.rx = X;
          n.ry = Y;
          n.boost = boost;
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
              const al =
                (1 - d2 / LINK2) * 0.2 * cfg.link * breath * (1 + (a.boost + b.boost) * 2.6);
              ctx.strokeStyle = rgba(al);
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
          if (animated) {
            n.x += n.vx * dt;
            n.y += n.vy * dt;
            n.ph += 0.01 * n.tw * dt;
            if (n.x < -10) n.x = w + 10;
            else if (n.x > w + 10) n.x = -10;
            if (n.y < -10) n.y = h + 10;
            else if (n.y > h + 10) n.y = -10;
          }
          const tw = 0.55 + 0.45 * Math.sin(n.ph);
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
          if (animated) d.ph += 0.006 * dt;
          let px = d.x;
          let py = d.y;
          if (pOn) {
            const dx = px - pcx;
            const dy = py - pcy;
            const d2 = dx * dx + dy * dy;
            if (d2 < PR2) {
              const dd = Math.sqrt(d2) || 0.001;
              const f = 1 - dd / PRADIUS;
              const push = f * f * PUSH * 1.3 * pAlpha;
              px += (dx / dd) * push;
              py += (dy / dd) * push;
            }
          }
          const a = (0.32 + 0.32 * Math.sin(d.ph)) * breath;
          ctx.save();
          ctx.translate(px, py);
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
      // dt en frames de 60fps, capado a 3 (janks/120Hz no aceleran el campo).
      const dt = last === 0 ? 1 : Math.min(3, (ts - last) / FRAME);
      last = ts;
      draw(true, dt);
      raf = requestAnimationFrame(loop);
    }

    resize();
    if (reduced) {
      // §2.3: con reduce, un único frame estático — atmósfera sin movimiento.
      draw(false, 1);
    } else {
      raf = requestAnimationFrame(loop);
    }

    // Pausa total cuando la pestaña no está visible: cero CPU en background.
    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(raf);
      } else if (!reduced && !running) {
        // `!running` defiende de un "visible" duplicado (webviews disparan
        // visibilitychange junto con focus/pageshow): sin el guard se
        // encadenaria un segundo rAF y el campo correria a 2x para siempre.
        running = true;
        last = 0; // evita un dt gigante al volver
        raf = requestAnimationFrame(loop);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    const onResize = () => resize();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onResize) : null;
    if (ro) ro.observe(host);
    else window.addEventListener("resize", onResize);

    // Cursor: se escucha en window (el host es pointer-events-none) y se
    // guardan coords relativas. Sale suave al dejar la ventana.
    let onMove: ((e: PointerEvent) => void) | null = null;
    let onLeave: (() => void) | null = null;
    if (cfg.pointer && !reduced) {
      onMove = (e) => {
        // §2.1: en touch/mobile no hay cursor — queda el campo en deriva.
        // Un tap o un scroll tactil no deben prender el halo de presencia.
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
      // Snapshot para el próximo mount del efecto: mismas posiciones y
      // mismo tiempo — un cambio de color re-tiñe con cero salto visual.
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
  }, [cfg, modeId, dens, dark, reduced]);

  const mask = MASKS[concentrate ?? cfg.concentrate];

  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 -z-10 select-none overflow-hidden",
        className,
      )}
    >
      {/* Capa canvas con fade-mask: baja opacidad por diseño — es atmósfera,
          no protagonista (§2.3). */}
      <div
        className="absolute inset-0"
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
