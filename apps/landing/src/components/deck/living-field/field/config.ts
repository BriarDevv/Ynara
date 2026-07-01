/**
 * **Configuración del campo vivo** — params por variante + constantes de
 * física. Compartido web/mobile: ambos renderers leen de acá, así una variante
 * (densidad, link, aura, etc.) se ve igual en las dos plataformas.
 *
 * Cada pantalla destaca UNA textura (DESIGN.md §2.2).
 */

export type LivingFieldVariant = "aurora" | "constellation" | "network" | "paper" | "depth";

export type FieldDensity = "sutil" | "media" | "intensa";

export type VariantConfig = {
  /** Ondas de marca (cintas + hilos). */
  waves: boolean;
  /** Campo de nodos (estrellas + hilos + diamantes). */
  particles: boolean;
  /** Reactividad al cursor (web: halo + repulsión; mobile: sin cursor). */
  pointer: boolean;
  density: FieldDensity;
  /** Énfasis de los hilos entre nodos. */
  link: number;
  /** Opacidad del grano (capa estática). */
  grain: number;
  /** Fuerza de los blooms de profundidad. */
  aura: number;
  concentrate: "top" | "full";
};

export const VARIANTS: Record<LivingFieldVariant, VariantConfig> = {
  // Hoy: ondas que fluyen + atmósfera.
  aurora: {
    waves: true,
    particles: true,
    pointer: true,
    density: "sutil",
    link: 0.8,
    grain: 0.1,
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
    grain: 0.08,
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
    grain: 0.08,
    aura: 0.9,
    concentrate: "full",
  },
  // Agenda: limpio, casi quieto, sin cursor.
  paper: {
    waves: false,
    particles: true,
    pointer: false,
    density: "sutil",
    link: 0.25,
    grain: 0.05,
    aura: 0.5,
    concentrate: "top",
  },
  // Tú/perfil: profundidad pura (blooms, sin partículas).
  depth: {
    waves: false,
    particles: false,
    pointer: false,
    density: "sutil",
    link: 1,
    grain: 0.08,
    aura: 1.6,
    concentrate: "full",
  },
};

export const DENSITY_FACTOR: Record<FieldDensity, number> = {
  sutil: 0.55,
  media: 1,
  intensa: 1.7,
};

/**
 * Fade-mask: concentra el campo arriba (zona de presencia) y lo desvanece bajo
 * el texto — el contraste se mide contra el plano, no contra la atmósfera
 * (§3.8). Strings CSS para web; en Skia se traducen a un gradiente de máscara
 * equivalente (mismas paradas).
 */
export const MASKS = {
  top: "linear-gradient(180deg, #000 0%, #000 34%, rgba(0, 0, 0, 0.5) 68%, transparent 98%)",
  full: "radial-gradient(125% 95% at 50% 0%, #000 0%, #000 30%, transparent 86%)",
} as const;

/** Constantes de física del campo (distancias en px). */
export const FIELD = {
  /** Distancia de enlace entre nodos. */
  LINK: 108,
  /** Radio de la fuerza del cursor. */
  PRADIUS: 175,
  /** Intensidad de la repulsión. */
  PUSH: 22,
} as const;

export const LINK2 = FIELD.LINK * FIELD.LINK;
export const PR2 = FIELD.PRADIUS * FIELD.PRADIUS;

/**
 * Cantidad de nodos: acotada por área (§2.3), cap duro de 130. En mobile el
 * área chica baja el count solo. Misma fórmula en ambas plataformas.
 */
export function nodeCount(w: number, h: number, factor: number): number {
  return Math.max(10, Math.min(130, Math.round(((w * h) / 12500) * factor)));
}

/** Cantidad de diamantes: ~12% de los nodos, mínimo 2. */
export function diamondCount(nodes: number): number {
  return Math.max(2, Math.round(nodes * 0.12));
}
