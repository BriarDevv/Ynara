// Geometría del sistema gráfico "Red de memoria" (DESIGN.md §2).
//
// Capa portable (data, sin DOM): genera nodos + vínculos de forma
// **determinista** (PRNG sembrado, sin Math.random/Date) para que el
// render sea idéntico en server y cliente (no rompe la hidratación SSR)
// y estable entre builds. El renderer web (`MemoryField.tsx`) la dibuja;
// un renderer RN futuro mapea las mismas formas a react-native-svg.

export type FieldDensity = "dispersa" | "media" | "densa";

/** Nodo: una idea/recuerdo. `diamond` = acento rítmico (presencia). */
export type FieldNode = { x: number; y: number; r: number; diamond: boolean };

/** Vínculo: hilo curvo (Bézier cuadrática) entre dos nodos. */
export type FieldLink = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  cx: number;
  cy: number;
};

export type MemoryFieldGeometry = {
  width: number;
  height: number;
  nodes: FieldNode[];
  links: FieldLink[];
};

const WIDTH = 1200;
const HEIGHT = 800;

const GRID: Record<FieldDensity, { cols: number; rows: number }> = {
  dispersa: { cols: 5, rows: 3 },
  media: { cols: 7, rows: 4 },
  densa: { cols: 9, rows: 6 },
};

/** PRNG determinista (mulberry32). Mismo seed → misma secuencia. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const round = (n: number) => Math.round(n * 10) / 10;

/**
 * Genera una red orgánica: nodos en una grilla con jitter (distribución
 * pareja pero no mecánica) y vínculos curvos entre vecinos de grilla.
 * Algunos nodos son diamantes (acentos). Todo derivado del `seed`.
 */
export function buildMemoryField(density: FieldDensity, seed: number): MemoryFieldGeometry {
  const rand = mulberry32(seed);
  const { cols, rows } = GRID[density];
  const cellW = WIDTH / cols;
  const cellH = HEIGHT / rows;

  const nodes: FieldNode[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = round(c * cellW + (0.25 + rand() * 0.5) * cellW);
      const y = round(r * cellH + (0.25 + rand() * 0.5) * cellH);
      const radius = round(3 + rand() * 2.5);
      const diamond = rand() < 0.16;
      nodes.push({ x, y, r: radius, diamond });
    }
  }

  const at = (c: number, r: number) => nodes[r * cols + c];
  const links: FieldLink[] = [];
  const tryLink = (a: FieldNode, b: FieldNode | undefined) => {
    if (!b || rand() > 0.62) return;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy) || 1;
    const off = (rand() - 0.5) * 70;
    links.push({
      x1: a.x,
      y1: a.y,
      x2: b.x,
      y2: b.y,
      // Punto de control = punto medio desplazado en la perpendicular.
      cx: round((a.x + b.x) / 2 + (-dy / len) * off),
      cy: round((a.y + b.y) / 2 + (dx / len) * off),
    });
  };
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const a = at(c, r);
      if (!a) continue;
      if (c < cols - 1) tryLink(a, at(c + 1, r));
      if (r < rows - 1) tryLink(a, at(c, r + 1));
    }
  }

  return { width: WIDTH, height: HEIGHT, nodes, links };
}
