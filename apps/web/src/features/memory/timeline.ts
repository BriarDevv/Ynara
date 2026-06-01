import type {
  EpisodicMemoryOut,
  MemoryItemOut,
  MemoryLayer,
  MemoryList,
  ProceduralMemoryOut,
  SemanticMemoryOut,
} from "@ynara/shared-schemas";

/**
 * Una entrada normalizada del timeline de memoria. Aplana las 3 capas (que
 * tienen shapes distintos) a un modelo común para renderizar una sola lista
 * cronológica. `ref` es el identificador de detalle: UUID en semantic/episodic,
 * `key` en procedural — el que consume `GET /v1/memory/{layer}/{ref}`.
 */
export type TimelineEntry = {
  layer: MemoryLayer;
  ref: string;
  title: string;
  /** Fecha canónica de la entrada (ISO), la que ordena el timeline. */
  date: string;
};

/** Capa semántica: la fecha es `created_at`, el título es el hecho. */
function semanticToEntry(item: SemanticMemoryOut): TimelineEntry {
  return { layer: "semantic", ref: item.id, title: item.content, date: item.created_at };
}

/** Capa episódica: la fecha es `occurred_at` (cuándo pasó), el título el resumen. */
function episodicToEntry(item: EpisodicMemoryOut): TimelineEntry {
  return { layer: "episodic", ref: item.id, title: item.summary, date: item.occurred_at };
}

/**
 * Convierte una `key` técnica (`foco_horario`) en un título legible
 * (`Foco horario`): separa por `_`/`-` y capitaliza la primera palabra.
 */
export function humanizeKey(key: string): string {
  const words = key.replace(/[_-]+/g, " ").trim();
  if (!words) return key;
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Capa procedural: la fecha es `last_reinforced_at`, el título humaniza la key. */
function proceduralToEntry(item: ProceduralMemoryOut): TimelineEntry {
  return {
    layer: "procedural",
    ref: item.key,
    title: humanizeKey(item.key),
    date: item.last_reinforced_at,
  };
}

/** Orden cronológico descendente (lo más reciente primero). */
function byDateDesc(a: TimelineEntry, b: TimelineEntry): number {
  return b.date.localeCompare(a.date);
}

/**
 * Aplana la respuesta agrupada de `GET /v1/memory` a un timeline único
 * ordenado por fecha descendente.
 */
export function toTimelineEntries(list: MemoryList): TimelineEntry[] {
  return [
    ...list.semantic.items.map(semanticToEntry),
    ...list.episodic.items.map(episodicToEntry),
    ...list.procedural.items.map(proceduralToEntry),
  ].sort(byDateDesc);
}

/** Entradas de una sola capa (cuando hay un filtro `?layer=` activo). */
export function entriesForLayer(
  layer: MemoryLayer,
  items: SemanticMemoryOut[] | EpisodicMemoryOut[] | ProceduralMemoryOut[],
): TimelineEntry[] {
  const mapped: TimelineEntry[] =
    layer === "semantic"
      ? (items as SemanticMemoryOut[]).map(semanticToEntry)
      : layer === "episodic"
        ? (items as EpisodicMemoryOut[]).map(episodicToEntry)
        : (items as ProceduralMemoryOut[]).map(proceduralToEntry);
  return mapped.sort(byDateDesc);
}

// ---------- Relacionados ----------

/**
 * La sesión de origen de un ítem, según la capa: `source_session_id` en
 * semantic, `session_id` en episodic, `null` en procedural (no nace de una
 * sesión). Es la clave para encontrar memorias hermanas.
 */
export function sessionRefOf(layer: MemoryLayer, item: MemoryItemOut): string | null {
  if (layer === "semantic") return (item as SemanticMemoryOut).source_session_id;
  if (layer === "episodic") return (item as EpisodicMemoryOut).session_id;
  return null;
}

/**
 * Memorias que comparten la sesión `sessionId`, excluyendo la actual
 * (`excludeLayer`/`excludeRef`). Derivación de cliente: no hay endpoint de
 * relacionados, así que se cruzan los ítems de la lista por su sesión de
 * origen. Devuelve hasta 3 entradas, ordenadas por fecha desc. Procedural no
 * tiene sesión → si `sessionId` es null, no hay relacionados.
 */
export function relatedEntries(
  list: MemoryList,
  opts: { sessionId: string | null; excludeLayer: MemoryLayer; excludeRef: string },
): TimelineEntry[] {
  if (opts.sessionId === null) return [];

  const siblings: TimelineEntry[] = [];
  for (const item of list.semantic.items) {
    if (item.source_session_id !== opts.sessionId) continue;
    if (opts.excludeLayer === "semantic" && item.id === opts.excludeRef) continue;
    siblings.push(semanticToEntry(item));
  }
  for (const item of list.episodic.items) {
    if (item.session_id !== opts.sessionId) continue;
    if (opts.excludeLayer === "episodic" && item.id === opts.excludeRef) continue;
    siblings.push(episodicToEntry(item));
  }
  return siblings.sort(byDateDesc).slice(0, 3);
}

// ---------- Agrupado por bucket temporal ----------

export type TimelineGroup = {
  /** Etiqueta del bucket (`Hoy`, `Esta semana`, …). */
  bucket: string;
  entries: TimelineEntry[];
};

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Agrupa entradas (ya ordenadas) en buckets relativos a `now`. `now` se inyecta
 * para tests deterministas; en runtime el caller pasa `new Date()`. Conserva el
 * orden descendente dentro de cada bucket y descarta buckets vacíos.
 */
export function groupByBucket(entries: TimelineEntry[], now: Date): TimelineGroup[] {
  const nowMs = now.getTime();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();

  // El último bucket (`test: () => true`) captura todo lo no clasificado; al
  // estar fuera del array es un valor garantizado (no `T | undefined`) y sirve
  // de fallback para `find`.
  const fallback = { label: "Hace tiempo", test: () => true };
  const buckets: { label: string; test: (ms: number) => boolean }[] = [
    { label: "Hoy", test: (ms) => ms >= startOfToday },
    { label: "Esta semana", test: (ms) => ms >= nowMs - 7 * DAY_MS },
    { label: "Este mes", test: (ms) => ms >= nowMs - 30 * DAY_MS },
    fallback,
  ];

  const grouped = new Map<string, TimelineEntry[]>();
  for (const entry of entries) {
    const ms = new Date(entry.date).getTime();
    const bucket = buckets.find((b) => b.test(ms)) ?? fallback;
    const list = grouped.get(bucket.label) ?? [];
    list.push(entry);
    grouped.set(bucket.label, list);
  }

  // Reconstruye en el orden canónico de buckets, salteando los vacíos.
  return buckets
    .filter((b) => grouped.has(b.label))
    .map((b) => ({ bucket: b.label, entries: grouped.get(b.label) ?? [] }));
}

const MONTHS_ES = [
  "ene",
  "feb",
  "mar",
  "abr",
  "may",
  "jun",
  "jul",
  "ago",
  "sep",
  "oct",
  "nov",
  "dic",
];

/** Fecha absoluta con hora para el detalle: `8 may 2026 · 09:42`. */
export function formatFullDate(iso: string): string {
  const date = new Date(iso);
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${date.getDate()} ${MONTHS_ES[date.getMonth()]} ${date.getFullYear()} · ${hh}:${mm}`;
}

/**
 * Fecha corta y humana para la meta de una entrada, relativa a `now`:
 * `hoy 09:42` / `ayer` / `hace 3 días` (≤7) / `8 may` para lo más viejo.
 * `now` inyectable para tests deterministas.
 */
export function formatEntryDate(iso: string, now: Date): string {
  const date = new Date(iso);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const daysAgo = Math.round((startOfToday - startOfDate) / DAY_MS);

  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");

  if (daysAgo <= 0) return `hoy ${hh}:${mm}`;
  if (daysAgo === 1) return "ayer";
  if (daysAgo <= 7) return `hace ${daysAgo} días`;
  return `${date.getDate()} ${MONTHS_ES[date.getMonth()]}`;
}
