import type {
  EpisodicMemoryOut,
  MemoryItemOut,
  MemoryLayer,
  ProceduralMemoryOut,
  SemanticMemoryOut,
} from "@ynara/shared-schemas";
import { humanizeKey } from "./timeline";

export type DetailMeta = { label: string; value: string };

/**
 * Lo que el detalle muestra de un ítem, ya resuelto por capa para que el JSX no
 * tenga ramas. `quote` es el texto grande (el recuerdo en sí); `dateIso` la
 * fecha canónica; `meta` las filas de contexto; `tags` los tópicos/valores;
 * `note` un aviso cuando aplica (sensible, sin reforzar).
 */
export type DetailPresentation = {
  quote: string;
  dateIso: string;
  /** Si el ítem nació de una sesión (para el bloque "Contexto original"). */
  fromSession: boolean;
  meta: DetailMeta[];
  tags: string[];
  note?: string;
};

/** Convierte un dict (topics/value) en tags legibles `clave: valor`. */
function tagsFromRecord(rec: Record<string, unknown>): string[] {
  return Object.entries(rec).map(([k, v]) => {
    const value = typeof v === "object" && v !== null ? JSON.stringify(v) : String(v);
    return `${humanizeKey(k)}: ${value}`;
  });
}

function presentSemantic(item: SemanticMemoryOut): DetailPresentation {
  const meta: DetailMeta[] = [];
  if (item.importance !== null)
    meta.push({ label: "Importancia", value: `${item.importance}/100` });
  return {
    quote: item.content,
    dateIso: item.created_at,
    fromSession: item.source_session_id !== null,
    meta,
    tags: [],
  };
}

function presentEpisodic(item: EpisodicMemoryOut): DetailPresentation {
  return {
    quote: item.summary,
    dateIso: item.occurred_at,
    fromSession: true,
    meta: [{ label: "Retención", value: `${item.retention_days} días` }],
    tags: tagsFromRecord(item.topics),
    note: item.is_sensitive ? "Recuerdo sensible — se guarda con cuidado extra." : undefined,
  };
}

function presentProcedural(item: ProceduralMemoryOut): DetailPresentation {
  return {
    quote: humanizeKey(item.key),
    dateIso: item.last_reinforced_at,
    fromSession: false,
    meta: [{ label: "Confianza", value: `${Math.round(item.confidence * 100)}%` }],
    tags: tagsFromRecord(item.value),
    note: item.stale ? "Hace rato que no se refuerza." : undefined,
  };
}

/** Resuelve la presentación del detalle según la capa. */
export function presentDetail(layer: MemoryLayer, item: MemoryItemOut): DetailPresentation {
  if (layer === "semantic") return presentSemantic(item as SemanticMemoryOut);
  if (layer === "episodic") return presentEpisodic(item as EpisodicMemoryOut);
  return presentProcedural(item as ProceduralMemoryOut);
}
