import { buildMemoryField, type FieldDensity, type FieldNode } from "./field";

export type MemoryFieldProps = {
  /** Protagonismo de la superficie (DESIGN.md §2.2). Default "media". */
  density?: FieldDensity;
  /** Clara (azul/memoria sobre marfil) o nocturna (niebla). Default "clara". */
  variant?: "clara" | "nocturna";
  /** Semilla del layout. Mismo seed → misma red (estable SSR/build). */
  seed?: number;
  className?: string;
};

type VariantTokens = {
  link: string;
  linkOpacity: number;
  halo: number;
  node: number;
  diamond: number;
};

// Colores siempre vía tokens de la rampa de memoria (DESIGN.md §3.4),
// nunca hex. Las opacidades mantienen la red como ambiente detrás del
// contenido (§2.5: nunca tapar texto).
const VARIANTS: Record<"clara" | "nocturna", VariantTokens> = {
  clara: { link: "var(--color-memory)", linkOpacity: 0.2, halo: 0.1, node: 0.85, diamond: 0.7 },
  nocturna: {
    link: "var(--color-memory-soft)",
    linkOpacity: 0.26,
    halo: 0.14,
    node: 0.95,
    diamond: 0.8,
  },
};

function diamond(n: FieldNode): string {
  const s = n.r * 2.2;
  return `M${n.x} ${n.y - s} L${n.x + s} ${n.y} L${n.x} ${n.y + s} L${n.x - s} ${n.y} Z`;
}

/**
 * Fondo ambiental "Red de memoria" (DESIGN.md §2): nodos + vínculos
 * curvos + diamantes como acento. SVG estático (sin loops, §2.5/§8) que
 * llena su contenedor (`width/height 100%` + `preserveAspectRatio slice`);
 * el consumidor lo envuelve en un contenedor posicionado. Decorativo.
 */
export function MemoryField({
  density = "media",
  variant = "clara",
  seed = 7,
  className,
}: MemoryFieldProps) {
  const { width, height, nodes, links } = buildMemoryField(density, seed);
  const v = VARIANTS[variant];

  return (
    <svg
      className={className}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
      aria-hidden={true}
      focusable={false}
      style={{ pointerEvents: "none" }}
    >
      <g stroke={v.link} strokeWidth={1.2} strokeOpacity={v.linkOpacity} strokeLinecap="round">
        {links.map((l) => (
          <path
            key={`${l.x1},${l.y1}-${l.x2},${l.y2}`}
            d={`M${l.x1} ${l.y1} Q${l.cx} ${l.cy} ${l.x2} ${l.y2}`}
          />
        ))}
      </g>
      <g>
        {nodes.map((n) =>
          n.diamond ? (
            <path
              key={`${n.x},${n.y},${n.r}`}
              d={diamond(n)}
              stroke="var(--color-memory-accent)"
              strokeOpacity={v.diamond}
              strokeWidth={1.6}
            />
          ) : (
            <g key={`${n.x},${n.y},${n.r}`}>
              <circle
                cx={n.x}
                cy={n.y}
                r={n.r * 2.6}
                fill="var(--color-memory-soft)"
                fillOpacity={v.halo}
              />
              <circle
                cx={n.x}
                cy={n.y}
                r={n.r}
                fill="var(--color-memory-soft)"
                fillOpacity={v.node}
              />
            </g>
          ),
        )}
      </g>
    </svg>
  );
}
