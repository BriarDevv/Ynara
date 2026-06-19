import { hexToRgb, MODE_CLIMATE, type ModeClimate, type Rgb } from "./climate";
import { diamondCount, FIELD, nodeCount } from "./config";

/**
 * **Modelo puro del campo vivo** — estado (nodos/diamantes), su evolución por
 * frame, y los "specs" de blooms y ondas. Es la fuente ÚNICA de la geometría y
 * la animación: cada plataforma (web Canvas2D / mobile Skia) sólo traduce estos
 * specs a sus propias llamadas de dibujo, así el resultado es idéntico.
 *
 * Sin DOM, sin React, sin canvas: matemática pura + tipos. Las funciones que
 * mutan estado (`stepNodes`, `stepDiamonds`) lo hacen in-place por performance
 * (se llaman cada frame); el resto es puro.
 */

export type FieldNode = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  ph: number;
  tw: number;
  glow: boolean;
  /** Posición de render (deriva + repulsión del cursor), recalculada por frame. */
  rx: number;
  ry: number;
  boost: number;
};

export type FieldDiamond = {
  x: number;
  y: number;
  s: number;
  ph: number;
  filled: boolean;
};

export type FieldGeometry = {
  nodes: FieldNode[];
  diamonds: FieldDiamond[];
};

/** Fuente de aleatoriedad inyectable (default `Math.random`). Permite sembrar
 *  determinístico si se quiere el MISMO campo en ambas plataformas. */
export type Rng = () => number;

function rangeWith(rng: Rng) {
  return (a: number, b: number) => a + rng() * (b - a);
}

/**
 * Siembra la geometría del campo para un tamaño dado. `particles=false`
 * (variante `depth`) devuelve listas vacías (sólo blooms). Misma fórmula de
 * conteo y mismos rangos que el original — el carácter del campo no cambia.
 */
export function seedField(
  w: number,
  h: number,
  factor: number,
  particles: boolean,
  rng: Rng = Math.random,
): FieldGeometry {
  if (!particles) return { nodes: [], diamonds: [] };
  const rand = rangeWith(rng);
  const count = nodeCount(w, h, factor);
  const nodes: FieldNode[] = [];
  for (let i = 0; i < count; i++) {
    nodes.push({
      x: rng() * w,
      y: rng() * h,
      vx: rand(-0.09, 0.09),
      vy: rand(-0.09, 0.09),
      r: rand(0.8, 2.4),
      ph: rng() * Math.PI * 2,
      tw: rand(0.6, 1.4),
      glow: rng() > 0.82,
      rx: 0,
      ry: 0,
      boost: 0,
    });
  }
  const dc = diamondCount(count);
  const diamonds: FieldDiamond[] = [];
  for (let i = 0; i < dc; i++) {
    diamonds.push({
      x: rng() * w,
      y: rng() * h,
      s: rand(4, 8),
      ph: rng() * Math.PI * 2,
      filled: rng() > 0.5,
    });
  }
  return { nodes, diamonds };
}

/** Avanza el reloj del campo. `dt` en frames de 60fps (1 = 16.67ms). */
export function advanceTime(t: number, dt: number): number {
  return t + 0.0045 * dt;
}

/** Respiración global (escala alphas y movimiento). */
export function breath(t: number): number {
  return 0.62 + 0.38 * Math.sin(t * 1.3);
}

/** Titileo de un nodo a partir de su fase. */
export function nodeTwinkle(ph: number): number {
  return 0.55 + 0.45 * Math.sin(ph);
}

/** Evolución in-place de los nodos: deriva + wrap + avance de fase. */
export function stepNodes(nodes: FieldNode[], dt: number, w: number, h: number): void {
  for (const n of nodes) {
    n.x += n.vx * dt;
    n.y += n.vy * dt;
    n.ph += 0.01 * n.tw * dt;
    if (n.x < -10) n.x = w + 10;
    else if (n.x > w + 10) n.x = -10;
    if (n.y < -10) n.y = h + 10;
    else if (n.y > h + 10) n.y = -10;
  }
}

/** Evolución in-place de los diamantes: avance de fase. */
export function stepDiamonds(diamonds: FieldDiamond[], dt: number): void {
  for (const d of diamonds) d.ph += 0.006 * dt;
}

/**
 * Repulsión suave del cursor sobre un punto. Devuelve la posición desplazada +
 * el "boost" (0..1) para iluminarlo. `mult` sube la fuerza (los diamantes usan
 * 1.3). En mobile, sin cursor, no se llama (los renders pasan la posición cruda).
 */
export function repel(
  x: number,
  y: number,
  pcx: number,
  pcy: number,
  pAlpha: number,
  mult = 1,
): { x: number; y: number; boost: number } {
  const dx = x - pcx;
  const dy = y - pcy;
  const d2 = dx * dx + dy * dy;
  if (d2 >= FIELD.PRADIUS * FIELD.PRADIUS) return { x, y, boost: 0 };
  const d = Math.sqrt(d2) || 0.001;
  const f = 1 - d / FIELD.PRADIUS; // 0 en el borde, 1 en el centro
  const push = f * f * FIELD.PUSH * mult * pAlpha;
  return { x: x + (dx / d) * push, y: y + (dy / d) * push, boost: f * pAlpha };
}

/** Alpha de un hilo entre dos nodos según su distancia² y los boosts. */
export function linkAlpha(d2: number, link: number, br: number, boostSum: number): number {
  const LINK2 = FIELD.LINK * FIELD.LINK;
  return (1 - d2 / LINK2) * 0.2 * link * br * (1 + boostSum * 2.6);
}

// ── Blooms de profundidad ────────────────────────────────────────────────────

export type BloomSpec = {
  cx: number;
  cy: number;
  r: number;
  rgb: Rgb;
  /** Alpha del centro; el borde es 0 (gradiente radial). */
  alpha: number;
};

/** Los 2 blooms ambientales (vacío si `aura<=0`). Derivan lento con `t`. */
export function buildBlooms(
  w: number,
  h: number,
  t: number,
  dark: boolean,
  aura: number,
  climate: ModeClimate,
): BloomSpec[] {
  if (aura <= 0) return [];
  const dx = Math.sin(t * 0.3) * w * 0.03;
  const dy = Math.cos(t * 0.26) * h * 0.03;
  const rad = Math.max(w, h);
  return [
    {
      cx: w * 0.26 + dx,
      cy: h * 0.02 + dy,
      r: rad * 0.62,
      rgb: hexToRgb(climate.a),
      alpha: (dark ? 0.4 : 0.28) * aura,
    },
    {
      cx: w * 0.82 - dx,
      cy: -h * 0.02 + dy,
      r: rad * 0.55,
      rgb: hexToRgb(climate.b),
      alpha: (dark ? 0.32 : 0.22) * aura,
    },
  ];
}

// ── Ondas de marca (cintas + hilos) ──────────────────────────────────────────

export const RIBBONS = 7;
export const THREADS = 5;
export const RIBBON_STEP = 12;
export const THREAD_STEP = 10;
const TAU = 6.2832;

export type RibbonSpec = {
  cy: number;
  amp: number;
  thick: number;
  wl: number;
  ph: number;
  rgb: Rgb;
  /** Alpha del extremo derecho del gradiente (izq→der). */
  aEnd: number;
};

export type ThreadSpec = {
  cy: number;
  amp: number;
  wl: number;
  ph: number;
  rgb: Rgb;
  aEnd: number;
};

/** Paleta de las ondas (§3.4): clima a/b + 3 stops oficiales. */
function waveColors(climate: ModeClimate): Rgb[] {
  return [
    hexToRgb(climate.a),
    hexToRgb(climate.b),
    hexToRgb(MODE_CLIMATE.memoria.b), // lavanda
    hexToRgb(MODE_CLIMATE.bienestar.a), // violeta
    hexToRgb(MODE_CLIMATE.productividad.b), // celeste
  ];
}

/** Specs de las cintas + hilos. El renderer samplea las curvas con `ribbonEdgeY`
 *  / `threadY` y aplica los gradientes (izq→der). */
export function buildWaves(
  w: number,
  h: number,
  t: number,
  br: number,
  dark: boolean,
  climate: ModeClimate,
): { ribbons: RibbonSpec[]; threads: ThreadSpec[] } {
  const cols = waveColors(climate);
  const ribbons: RibbonSpec[] = [];
  for (let k = 0; k < RIBBONS; k++) {
    ribbons.push({
      cy: h * (0.1 + k * 0.075),
      amp: h * (0.034 + k * 0.012),
      thick: h * (0.075 + (k % 3) * 0.022),
      wl: w * (0.9 + (k % 3) * 0.34),
      ph: t * (0.32 + k * 0.13),
      rgb: cols[k % cols.length] as Rgb,
      aEnd: (dark ? 0.34 : 0.25) * (0.84 + 0.16 * Math.sin(t * 0.4 + k * 0.9)) * (0.8 + 0.2 * br),
    });
  }
  const threads: ThreadSpec[] = [];
  for (let k = 0; k < THREADS; k++) {
    threads.push({
      cy: h * (0.12 + k * 0.1),
      amp: h * (0.045 + k * 0.014),
      wl: w * (0.96 + (k % 2) * 0.28),
      ph: t * (0.28 + k * 0.12) + k * 1.1,
      rgb: cols[(k + 1) % cols.length] as Rgb,
      aEnd: (dark ? 0.42 : 0.32) * (0.8 + 0.2 * br),
    });
  }
  return { ribbons, threads };
}

/** Y de un borde de cinta en `x`. `edge` = -1 (arriba) | +1 (abajo). */
export function ribbonEdgeY(x: number, r: RibbonSpec, edge: -1 | 1): number {
  const u = (x / r.wl) * TAU;
  return (
    r.cy +
    (edge * r.thick) / 2 +
    Math.sin(u + r.ph) * r.amp +
    Math.sin(u * 0.5 - r.ph * 1.2) * r.amp * 0.32
  );
}

/** Y de un hilo en `x`. */
export function threadY(x: number, th: ThreadSpec): number {
  const u = (x / th.wl) * TAU;
  return th.cy + Math.sin(u + th.ph) * th.amp + Math.sin(u * 0.5 - th.ph) * th.amp * 0.3;
}
