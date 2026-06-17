import { z } from "zod";

import { MemoryLayerSchema } from "./modes";

/**
 * Contrato de memoria — mirror de los endpoints `/v1/memory(/*)`.
 *
 * Fuente de verdad: `apps/backend/app/schemas/memory.py` (los `*Out` de las
 * 3 capas) + `apps/backend/docs/ENDPOINTS.md` (shapes de list/detail). Las
 * tablas de memoria son **sagradas** (regla #3), pero este archivo NO las
 * toca: es validación de cliente sobre las respuestas HTTP ya descifradas
 * (`content`/`summary` viajan en plaintext, el blob cifrado y el embedding
 * nunca salen del backend).
 *
 * Regla "Pydantic gana, Zod sigue": si el backend cambia el contrato, se
 * corrige este mirror en el mismo PR. El Pydantic ya existe para list/detail,
 * así que la divergencia es detectable en code review.
 *
 * El bloque de **búsqueda** (`MemorySearch*`) es **PROVISIONAL**: el endpoint
 * `GET /v1/memory/search` todavía no existe (es un endpoint-chico del track
 * backend, ver FRONTEND-APP-BUILD-PLAN §4 track-backend #1). Hasta que el
 * Pydantic se cierre, la UI corre contra el handler MSW que espeja este shape;
 * al cablear el endpoint real se mirrorea el Pydantic acá en el mismo PR.
 */

// ---------- Capa semántica (hechos) ----------

/** Mirror de `SemanticMemoryOut`. `content` ya descifrado. */
export const SemanticMemoryOutSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid(),
  content: z.string(),
  // Pydantic: `int | None` (0..100). La clave siempre viene, con `null` si no
  // se calculó importancia.
  importance: z.number().int().min(0).max(100).nullable(),
  source_session_id: z.string().uuid().nullable(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type SemanticMemoryOut = z.infer<typeof SemanticMemoryOutSchema>;

// ---------- Capa episódica (momentos) ----------

/** Mirror de `EpisodicMemoryOut`. `summary` ya descifrado. */
export const EpisodicMemoryOutSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid(),
  session_id: z.string().uuid(),
  summary: z.string(),
  is_sensitive: z.boolean(),
  retention_days: z.number().int(),
  occurred_at: z.string().datetime({ offset: true }),
  // Pydantic: `dict[str, Any]`. Espejamos como objeto laxo (metadata de tópicos).
  topics: z.record(z.unknown()),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type EpisodicMemoryOut = z.infer<typeof EpisodicMemoryOutSchema>;

// ---------- Capa procedural (costumbres) ----------

/** Mirror de `ProceduralMemoryOut`. Todos los campos derivados del decay. */
export const ProceduralMemoryOutSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid(),
  key: z.string(),
  value: z.record(z.unknown()),
  confidence: z.number(),
  last_reinforced_at: z.string().datetime({ offset: true }),
  stale: z.boolean(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type ProceduralMemoryOut = z.infer<typeof ProceduralMemoryOutSchema>;

// ---------- List (`GET /v1/memory`) ----------

/** Una rama paginada de una capa (`{ items, total }`). */
const layerPage = <T extends z.ZodTypeAny>(item: T) =>
  z.object({ items: z.array(item), total: z.number().int().nonnegative() });

export const SemanticMemoryPageSchema = layerPage(SemanticMemoryOutSchema);
export const EpisodicMemoryPageSchema = layerPage(EpisodicMemoryOutSchema);
export const ProceduralMemoryPageSchema = layerPage(ProceduralMemoryOutSchema);

/**
 * Respuesta de `GET /v1/memory` **sin** `?layer=`: las 3 capas agrupadas, cada
 * una con su página (`items`) y su `total` completo (para paginar).
 */
export const MemoryListSchema = z.object({
  semantic: SemanticMemoryPageSchema,
  episodic: EpisodicMemoryPageSchema,
  procedural: ProceduralMemoryPageSchema,
});
export type MemoryList = z.infer<typeof MemoryListSchema>;

// ---------- Detail (`GET /v1/memory/{layer}/{ref}`) ----------

/**
 * El detalle devuelve el `*Out` pelado de la capa (el caller conoce la capa por
 * la URL). Esta unión + el helper `memoryOutSchemaFor` permiten parsear con el
 * schema correcto según `layer` sin un discriminador embebido en el payload.
 */
export type MemoryItemOut = SemanticMemoryOut | EpisodicMemoryOut | ProceduralMemoryOut;

export const MEMORY_OUT_SCHEMA_BY_LAYER = {
  semantic: SemanticMemoryOutSchema,
  episodic: EpisodicMemoryOutSchema,
  procedural: ProceduralMemoryOutSchema,
} as const;

/** Devuelve el schema `*Out` de una capa. */
export function memoryOutSchemaFor(layer: z.infer<typeof MemoryLayerSchema>) {
  return MEMORY_OUT_SCHEMA_BY_LAYER[layer];
}

// ---------- Edición (`PATCH /v1/memory/{layer}/{ref}`) ----------

/**
 * Body de `PATCH` para la capa **semántica**: reemplaza `content` (el backend
 * re-embeddea + re-cifra). Mirror de la rama semantic de `MemoryPatchRequest`.
 */
export const SemanticMemoryPatchSchema = z.object({
  content: z.string().min(1).max(4096),
});
export type SemanticMemoryPatch = z.infer<typeof SemanticMemoryPatchSchema>;

/**
 * Body de `PATCH` para la capa **procedural**: reemplaza `value` de una key
 * existente (UPDATE puro, no resetea decay). Mirror de la rama procedural.
 * La capa **episódica** no admite PATCH (405): el `summary` lo genera el worker.
 */
export const ProceduralMemoryPatchSchema = z.object({
  value: z.record(z.unknown()),
});
export type ProceduralMemoryPatch = z.infer<typeof ProceduralMemoryPatchSchema>;

// ---------- Búsqueda (`GET /v1/memory/search?q=`) — PROVISIONAL ----------

/**
 * Un hit de búsqueda: una memoria rankeada por el store (`search()` =
 * embed + ANN + decrypt + rerank). No es una respuesta del LLM — son ítems de
 * memoria ordenados por relevancia. `ref` es UUID (semantic/episodic) o `key`
 * (procedural); `snippet` es el `content`/`summary`/`value` ya descifrado.
 */
export const MemorySearchHitSchema = z.object({
  layer: MemoryLayerSchema,
  ref: z.string().min(1),
  snippet: z.string(),
  /** Score de rerank, 0..1 (1 = más relevante). */
  score: z.number().min(0).max(1),
  /** Cuándo ocurrió/se creó la memoria, para ordenar/mostrar. */
  occurred_at: z.string().datetime({ offset: true }).nullable(),
});
export type MemorySearchHit = z.infer<typeof MemorySearchHitSchema>;

/** Respuesta de `GET /v1/memory/search?q=`. `total` = cantidad de hits. */
export const MemorySearchResponseSchema = z.object({
  query: z.string(),
  total: z.number().int().nonnegative(),
  results: z.array(MemorySearchHitSchema),
});
export type MemorySearchResponse = z.infer<typeof MemorySearchResponseSchema>;

// ---------- Export (`GET /v1/memory/export`) ----------

/**
 * Export JSON versionado de las 3 capas **completas** (sin paginar, descifradas).
 * Mirror de la respuesta de `GET /v1/memory/export`; el backend lo sirve además
 * con `Content-Disposition: attachment` (descarga directa del dueño).
 */
export const MemoryExportSchema = z.object({
  version: z.literal(1),
  exported_at: z.string().datetime({ offset: true }),
  semantic: z.array(SemanticMemoryOutSchema),
  episodic: z.array(EpisodicMemoryOutSchema),
  procedural: z.array(ProceduralMemoryOutSchema),
});
export type MemoryExport = z.infer<typeof MemoryExportSchema>;

// ---------- Wipe total (`POST /v1/memory/wipe`) — SAGRADO (regla #3) ----------

/**
 * Conteos por capa + total. Lo devuelve tanto el **preview** (`?dry_run=true`: lo
 * que se borraría) como el **result** (rowcounts REALES borrados). Solo enteros
 * (regla #4): nunca viaja `content` / `summary`.
 */
export const MemoryWipeCountsSchema = z.object({
  semantic: z.number().int().nonnegative(),
  episodic: z.number().int().nonnegative(),
  procedural: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
});
export type MemoryWipeCounts = z.infer<typeof MemoryWipeCountsSchema>;

/** Preview del wipe (`POST /v1/memory/wipe?dry_run=true`). Siempre 200, aun en 0. */
export const MemoryWipePreviewSchema = MemoryWipeCountsSchema;
export type MemoryWipePreview = z.infer<typeof MemoryWipePreviewSchema>;

/** Receipt del wipe ejecutado (rowcounts reales borrados). */
export const MemoryWipeResultSchema = MemoryWipeCountsSchema;
export type MemoryWipeResult = z.infer<typeof MemoryWipeResultSchema>;

/**
 * Body del **execute** (`POST /v1/memory/wipe`, sin `dry_run`): los conteos
 * per-capa que el cliente vio en un preview fresco (guarda de INTENCIÓN — prueba
 * que el humano vio el plan). Obligatorio; el backend lo valida con `extra=forbid`.
 */
export const MemoryWipeConfirmSchema = z.object({
  expected_semantic: z.number().int().nonnegative(),
  expected_episodic: z.number().int().nonnegative(),
  expected_procedural: z.number().int().nonnegative(),
});
export type MemoryWipeConfirm = z.infer<typeof MemoryWipeConfirmSchema>;

/**
 * `detail` del **409** (los `expected_*` no coinciden con el recount): los
 * conteos ACTUALES + un `message`, para re-confirmar con un preview fresco.
 * **Nada** se borró ni commiteó.
 */
export const MemoryWipeConflictSchema = z.object({
  message: z.string(),
  semantic: z.number().int().nonnegative(),
  episodic: z.number().int().nonnegative(),
  procedural: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
});
export type MemoryWipeConflict = z.infer<typeof MemoryWipeConflictSchema>;
