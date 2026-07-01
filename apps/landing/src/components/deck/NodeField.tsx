/**
 * CAMPO DE NODOS — el estado QUIETO de la corriente: nodos (puntos de luz),
 * vínculos (hilos) y diamantes (presencia) dispersos. Es el sistema del manual
 * de marca traído como elemento estructural (§4.2), no como ícono plano.
 *
 * Posiciones deterministas (sin Math.random → sin mismatch de hidratación).
 * Hereda `currentColor` → la lámina decide el tono (acento de registro).
 */

const NODES: ReadonlyArray<readonly [number, number]> = [
  [12, 20],
  [28, 12],
  [44, 24],
  [20, 40],
  [38, 46],
  [58, 16],
  [72, 30],
  [54, 40],
  [86, 22],
  [66, 52],
  [30, 64],
  [48, 70],
  [78, 62],
  [90, 48],
];

const LINKS: ReadonlyArray<readonly [number, number]> = [
  [0, 1],
  [1, 2],
  [0, 3],
  [3, 4],
  [2, 4],
  [2, 5],
  [5, 6],
  [6, 8],
  [4, 7],
  [7, 9],
  [6, 9],
  [9, 12],
  [12, 13],
  [8, 13],
  [4, 10],
  [10, 11],
  [11, 9],
  [3, 10],
];

// Nodos que llevan el "diamante de presencia".
const DIAMONDS = [4, 6, 9];

export function NodeField({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 80"
      className={className}
      fill="none"
      aria-hidden
      role="presentation"
      preserveAspectRatio="xMidYMid meet"
    >
      <g stroke="currentColor" strokeWidth="0.18" opacity="0.5">
        {LINKS.map(([a, b]) => (
          <line
            key={`l-${a}-${b}`}
            x1={NODES[a][0]}
            y1={NODES[a][1]}
            x2={NODES[b][0]}
            y2={NODES[b][1]}
          />
        ))}
      </g>
      <g fill="currentColor">
        {NODES.map(([x, y], i) => (
          <circle key={`n-${x}-${y}`} cx={x} cy={y} r={DIAMONDS.includes(i) ? 0 : 0.7} />
        ))}
      </g>
      <g fill="currentColor">
        {DIAMONDS.map((i) => {
          const [x, y] = NODES[i];
          return (
            <rect
              key={`d-${x}-${y}`}
              x={x - 1.4}
              y={y - 1.4}
              width={2.8}
              height={2.8}
              rx={0.5}
              transform={`rotate(45 ${x} ${y})`}
            />
          );
        })}
      </g>
    </svg>
  );
}
