/**
 * **Layout de columnas para eventos solapados** (CALENDAR-RESEARCH-2026 §1.4).
 *
 * Función pura y platform-agnostic: web (Canvas/DOM) y mobile (RN) la consumen
 * para acomodar los eventos concurrentes de una columna de día lado a lado, en
 * vez de pisarse. No conoce px ni fechas — opera sobre intervalos numéricos
 * (ej. minutos del día); cada render traduce `{col, cols}` a `left`/`width`.
 *
 * Algoritmo: ordenar por inicio → agrupar en *clusters* de solapamiento
 * transitivo → dentro del cluster, asignar cada evento a la primera columna
 * libre (greedy). El ancho de cada evento es `1/cols` de su cluster.
 */

export type LayoutInterval = {
  id: string;
  /** Inicio, en una unidad comparable (ej. minutos desde el inicio del día). */
  start: number;
  /** Fin (debe ser > `start`). */
  end: number;
};

export type ColumnPlacement = {
  /** Índice de columna (0-based) dentro del cluster. */
  col: number;
  /** Cantidad total de columnas del cluster (el divisor del ancho). */
  cols: number;
};

/**
 * Asigna a cada intervalo su `{col, cols}` para renderizarlo en columnas
 * lado-a-lado. Los que no se solapan con nadie quedan en `{col: 0, cols: 1}`
 * (ancho completo). Eventos que apenas se tocan (`end === start`) NO se
 * consideran solapados → comparten columna.
 */
export function layoutColumns(intervals: LayoutInterval[]): Map<string, ColumnPlacement> {
  const result = new Map<string, ColumnPlacement>();
  if (intervals.length === 0) return result;

  // Ordenar por inicio (asc); a igual inicio, el más largo primero (fin desc)
  // para que agarre la primera columna.
  const sorted = [...intervals].sort((a, b) => a.start - b.start || b.end - a.end);

  let cluster: LayoutInterval[] = [];
  let clusterEnd = Number.NEGATIVE_INFINITY;

  const flush = () => {
    if (cluster.length > 0) assignColumns(cluster, result);
    cluster = [];
    clusterEnd = Number.NEGATIVE_INFINITY;
  };

  for (const ev of sorted) {
    // Como están ordenados por inicio, si este arranca en/después del fin
    // máximo del cluster, no se solapa con nada de él → cerrar cluster.
    if (cluster.length > 0 && ev.start >= clusterEnd) flush();
    cluster.push(ev);
    clusterEnd = Math.max(clusterEnd, ev.end);
  }
  flush();

  return result;
}

/** Reparte un cluster ya formado en columnas (greedy: primera columna libre). */
function assignColumns(cluster: LayoutInterval[], out: Map<string, ColumnPlacement>): void {
  /** Fin del último evento colocado en cada columna. */
  const columnEnds: number[] = [];
  const colOf = new Map<string, number>();

  for (const ev of cluster) {
    let placed = false;
    for (let c = 0; c < columnEnds.length; c++) {
      const colEnd = columnEnds[c];
      if (colEnd !== undefined && ev.start >= colEnd) {
        columnEnds[c] = ev.end;
        colOf.set(ev.id, c);
        placed = true;
        break;
      }
    }
    if (!placed) {
      colOf.set(ev.id, columnEnds.length);
      columnEnds.push(ev.end);
    }
  }

  const cols = columnEnds.length;
  for (const ev of cluster) out.set(ev.id, { col: colOf.get(ev.id) ?? 0, cols });
}
